"""洛克王国伤害计算器 — 基于 NRC_AI 伤害公式的确定性伤害预测。

核心公式 (参考 NRC_AI):
  ability_level = (1 + atk_up + def_down) / max(0.1, 1 + atk_down + def_up)
  ATK = base_atk * ability_level
  base = (ATK / DEF) * power * 0.9
  damage = base * effectiveness * stab * weather_mult * hits * power_mult

4 阶段 hook 管线:
  pre_power → post_base → pre_final → post_calc
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from src.data.loader import (
    get_buff_stat_modifiers,
    get_skill_meta,
    get_skill_name,
    get_pet_species_stats,
    get_weather_damage_mult,
)
from src.game.type_chart import TypeChart
from src.analysis.constants import SDT_TO_TYPE

HookStage = Literal["pre_power", "post_base", "pre_final", "post_calc"]
DamageHook = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass
class DamageResult:
    skill_id: int
    skill_name: str
    power: int
    effective_power: int
    damage_type: int  # 2=物理, 3=特殊
    skill_element: int
    skill_element_name: str
    effectiveness: float
    effectiveness_label: str
    is_stab: bool
    expected_damage: int
    pct_hp: float  # 伤害占 defender 最大 HP 的百分比
    can_ko: bool
    energy_cost: int
    confidence: str  # "high" / "medium"
    hit_count: int = 1
    power_mult: float = 1.0
    weather_mult: float = 1.0
    damage_breakdown: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    # Backward-compatible properties — deterministic damage has no range
    @property
    def min_damage(self) -> int:
        return self.expected_damage

    @property
    def max_damage(self) -> int:
        return self.expected_damage

    @property
    def total_damage(self) -> int:
        return self.expected_damage * self.hit_count

    @property
    def total_min_damage(self) -> int:
        return self.total_damage

    @property
    def total_max_damage(self) -> int:
        return self.total_damage

    @property
    def pct_hp_range(self) -> Tuple[float, float]:
        return (self.pct_hp, self.pct_hp)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Add computed properties for backward compatibility
        d["min_damage"] = self.min_damage
        d["max_damage"] = self.max_damage
        d["total_damage"] = self.total_damage
        d["total_min_damage"] = self.total_min_damage
        d["total_max_damage"] = self.total_max_damage
        d["pct_hp_range"] = self.pct_hp_range
        return d


# 属性名到 stat name 的映射
_ATK_STAT = {2: "ATK", 3: "SPA"}  # damage_type → 攻击属性
_DEF_STAT = {2: "DEF", 3: "SPD"}  # damage_type → 防御属性

# STAB 倍率
_STAT_NAME_ALIASES = {
    "ATK": ("ATK", "ATTACK"),
    "DEF": ("DEF", "DEFENSE"),
    "SPA": ("SPA", "SPATK", "SP_ATTACK", "SPECIAL_ATTACK"),
    "SPD": ("SPD", "SPDEF", "SP_DEFENSE", "SPECIAL_DEFENSE"),
    "SPE": ("SPE", "SPEED", "SPD_SPEED"),
}
_STAB_MULTIPLIER = 1.5


class DamageCalculator:
    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self.chart = type_chart or TypeChart()
        self._hooks: Dict[HookStage, List[DamageHook]] = {
            "pre_power": [],
            "post_base": [],
            "pre_final": [],
            "post_calc": [],
        }

    def register_hook(self, stage: HookStage, hook: DamageHook) -> None:
        """注册伤害计算 hook。hook 接收并返回 context dict。"""
        if stage not in self._hooks:
            raise ValueError(f"Unknown hook stage: {stage}")
        self._hooks[stage].append(hook)

    def clear_hooks(self) -> None:
        """清除所有已注册的 hooks。"""
        for stage in self._hooks:
            self._hooks[stage].clear()

    def _run_hooks(self, stage: HookStage, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """依次执行某阶段的所有 hooks，返回最终 context。"""
        for hook in self._hooks[stage]:
            ctx = hook(ctx)
        return ctx

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def calculate(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        skill_meta: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
    ) -> Optional[DamageResult]:
        """计算单个技能的伤害预测。返回 None 如果不是攻击技能。"""
        power = self._get_power(skill_meta)
        damage_type = skill_meta.get("damage_type", 0)
        if power <= 0 or damage_type not in (2, 3):
            return None

        raw_dam_type = skill_meta.get("skill_dam_type", 0)
        skill_element = SDT_TO_TYPE.get(raw_dam_type, raw_dam_type)

        # Phase 1: Resolve power
        power, _ = self._resolve_power(power, skill_meta, attacker, defender)

        # Phase 2: Resolve combat stats
        stats = self._resolve_combat_stats(attacker, defender, damage_type, power)
        if stats is None:
            return None
        effective_atk, effective_def, ability_level, confidence, warnings, stat_sources = stats

        # Phase 3: Compute base damage
        base = self._compute_base_damage(power, effective_atk, effective_def, skill_meta, attacker, defender)

        # Phase 4: Apply multipliers (effectiveness, STAB, weather, hooks)
        mult_result = self._apply_multipliers(base, skill_element, attacker, defender, skill_meta, weather)
        dmg, effectiveness, stab_mult, weather_mult, power_mult, eff_label, is_stab = mult_result

        # Phase 5: Finalize (post_calc hooks, hit count, HP%, energy, result)
        return self._finalize_damage(
            dmg, power, ability_level, effective_atk, effective_def,
            effectiveness, stab_mult, weather_mult, power_mult,
            skill_meta, skill_element, attacker, defender,
            damage_type, eff_label, is_stab, confidence, warnings, stat_sources,
        )

    # ------------------------------------------------------------------
    # Calculation phases
    # ------------------------------------------------------------------

    def _resolve_power(
        self, power: int, skill_meta: Dict, attacker: Dict, defender: Dict,
    ) -> Tuple[int, Dict[str, Any]]:
        """阶段 1: pre_power hook — 可修正威力。"""
        ctx = self._run_hooks("pre_power", {
            "power": power,
            "skill_meta": skill_meta,
            "attacker": attacker,
            "defender": defender,
        })
        return ctx["power"], ctx

    def _resolve_combat_stats(
        self, attacker: Dict, defender: Dict, damage_type: int, power: int,
    ) -> Optional[Tuple[float, float, float, str, List[str], Dict[str, str]]]:
        """获取有效攻防属性、能力等级和置信度。返回 None 如果无法获取属性。"""
        confidence = "high"
        warnings: List[str] = []

        atk_name = _ATK_STAT[damage_type]
        def_name = _DEF_STAT[damage_type]
        base_atk, atk_source = self._get_stat_with_source(attacker, atk_name)
        base_def, def_source = self._get_stat_with_source(defender, def_name)

        if base_atk is None:
            base_atk = self._get_wiki_stat(attacker, atk_name)
            atk_source = "wiki"
        if base_def is None:
            base_def = self._get_wiki_stat(defender, def_name)
            def_source = "wiki"

        if base_atk is None or base_def is None:
            return None

        # 置信度分级: high(total 存在) / medium(calc+bonus) / low(wiki 估算)
        sources = {atk_source, def_source}
        if "wiki" in sources:
            confidence = "low"
            if atk_source == "wiki":
                warnings.append("攻击属性来自 wiki 估算")
            if def_source == "wiki":
                warnings.append("防御属性来自 wiki 估算")
        elif "calc_bonus" in sources:
            confidence = "medium"
            if atk_source == "calc_bonus":
                warnings.append("攻击属性来自 calc+bonus 估算")
            if def_source == "calc_bonus":
                warnings.append("防御属性来自 calc+bonus 估算")

        atk_mods = get_buff_stat_modifiers(attacker.get("buffs", []))
        def_mods = get_buff_stat_modifiers(defender.get("buffs", []))
        atk_up = atk_mods.get(f"{atk_name.lower()}_up", 0.0)
        atk_down = atk_mods.get(f"{atk_name.lower()}_down", 0.0)
        def_key = def_name.lower()
        def_up = def_mods.get(f"{def_key}_up", 0.0)
        def_down = def_mods.get(f"{def_key}_down", 0.0)

        ability_level = (1.0 + atk_up + def_down) / max(0.1, 1.0 + atk_down + def_up)
        ability_level = max(0.1, min(5.0, ability_level))

        effective_atk = base_atk * ability_level
        effective_def = max(1.0, float(base_def))

        if ability_level != 1.0:
            warnings.append(f"能力等级 ×{ability_level:.2f}")

        stat_sources = {
            "attack": atk_source,
            "defense": def_source,
            "attack_stat": atk_name,
            "defense_stat": def_name,
        }
        return effective_atk, effective_def, ability_level, confidence, warnings, stat_sources

    def _compute_base_damage(
        self, power: int, eff_atk: float, eff_def: float,
        skill_meta: Dict, attacker: Dict, defender: Dict,
    ) -> float:
        """阶段 2: 基础伤害公式 + post_base hook。"""
        base = self._base_damage(eff_atk, eff_def, power)
        ctx = self._run_hooks("post_base", {
            "base_damage": base,
            "power": power,
            "atk_val": eff_atk,
            "def_val": eff_def,
            "skill_meta": skill_meta,
            "attacker": attacker,
            "defender": defender,
        })
        return ctx["base_damage"]

    def _apply_multipliers(
        self,
        base: float, skill_element: int,
        attacker: Dict, defender: Dict, skill_meta: Dict,
        weather: Optional[Dict],
    ) -> Tuple[int, float, float, float, float, str, bool]:
        """阶段 3: 属性克制、STAB、天气、pre_final hook。"""
        defender_types = defender.get("types", [])
        effectiveness = self.chart.get_multiplier(skill_element, defender_types)
        eff_label = self.chart.get_effectiveness_label(effectiveness)

        attacker_types = attacker.get("types", [])
        is_stab = skill_element in attacker_types
        stab_mult = _STAB_MULTIPLIER if is_stab else 1.0

        weather_mult = get_weather_damage_mult(weather, skill_element)
        power_mult = 1.0

        ctx = self._run_hooks("pre_final", {
            "base_damage": base,
            "effectiveness": effectiveness,
            "stab_mult": stab_mult,
            "weather_mult": weather_mult,
            "power_mult": power_mult,
            "skill_meta": skill_meta,
            "attacker": attacker,
            "defender": defender,
        })
        base = ctx["base_damage"]
        effectiveness = ctx["effectiveness"]
        stab_mult = ctx["stab_mult"]
        weather_mult = ctx.get("weather_mult", weather_mult)
        power_mult = ctx.get("power_mult", power_mult)

        dmg = max(1, int(base * effectiveness * stab_mult * weather_mult * power_mult))
        return dmg, effectiveness, stab_mult, weather_mult, power_mult, eff_label, is_stab

    def _finalize_damage(
        self,
        dmg: int, power: int, ability_level: float,
        effective_atk: float, effective_def: float,
        effectiveness: float, stab_mult: float,
        weather_mult: float, power_mult: float,
        skill_meta: Dict, skill_element: int,
        attacker: Dict, defender: Dict,
        damage_type: int, eff_label: str, is_stab: bool,
        confidence: str, warnings: List[str], stat_sources: Dict[str, str],
    ) -> DamageResult:
        """阶段 4: post_calc hook、连击、HP%、能耗、构造结果。"""
        base_hits = self._get_base_hit_count(skill_meta)
        ctx = self._run_hooks("post_calc", {
            "min_damage": dmg,
            "max_damage": dmg,
            "hit_count": base_hits,
            "effectiveness": effectiveness,
            "stab_mult": stab_mult,
            "skill_meta": skill_meta,
            "attacker": attacker,
            "defender": defender,
        })
        dmg = ctx["min_damage"]

        hit_count = ctx.get("hit_count", 1)
        total_damage = dmg * hit_count

        defender_max_hp = defender.get("max_hp") or defender.get("current_hp") or 1
        defender_cur_hp = defender.get("current_hp") or 0
        pct = total_damage / defender_max_hp
        can_ko = total_damage >= defender_cur_hp

        energy_costs = skill_meta.get("energy_cost", [0])
        energy_cost = energy_costs[0] if energy_costs else 0
        if energy_cost > 0:
            attacker_energy = attacker.get("energy", 10)
            if attacker_energy < energy_cost:
                warnings.append(f"能量不足 (需要{energy_cost}, 当前{attacker_energy})")

        effective_power = int(power * stab_mult)
        breakdown = {
            "base_power": self._get_power(skill_meta),
            "effective_power": effective_power,
            "ability_level": round(ability_level, 3),
            "atk": int(effective_atk),
            "def_": int(effective_def),
            "effectiveness": effectiveness,
            "stab": stab_mult,
            "weather_mult": weather_mult,
            "power_mult": power_mult,
            "hit_count": hit_count,
            "stat_sources": stat_sources,
            "defender_current_hp": defender_cur_hp,
            "defender_max_hp": defender_max_hp,
        }

        return DamageResult(
            skill_id=skill_meta.get("id", 0),
            skill_name=skill_meta.get("name", "?"),
            power=self._get_power(skill_meta),
            effective_power=effective_power,
            damage_type=damage_type,
            skill_element=skill_element,
            skill_element_name=self.chart.type_name(skill_element) if skill_element else "无属性",
            effectiveness=effectiveness,
            effectiveness_label=eff_label,
            is_stab=is_stab,
            expected_damage=dmg,
            pct_hp=round(pct, 3),
            can_ko=can_ko,
            energy_cost=energy_cost,
            confidence=confidence,
            hit_count=hit_count,
            power_mult=power_mult,
            weather_mult=weather_mult,
            damage_breakdown=breakdown,
            warnings=warnings,
        )

    def calculate_all(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        skills: List[Dict[str, Any]],
        weather: Optional[Dict[str, Any]] = None,
    ) -> List[DamageResult]:
        """计算所有攻击技能的伤害预测，按最大伤害降序排列。"""
        results: List[DamageResult] = []
        for skill in skills:
            skill_id = skill.get("skill_id")
            if skill_id is None:
                continue
            meta = get_skill_meta(skill_id)
            if meta is None:
                continue
            result = self.calculate(attacker, defender, meta, weather=weather)
            if result is not None:
                results.append(result)
        results.sort(key=lambda r: r.total_max_damage, reverse=True)
        return results

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _base_damage(atk: float, def_: float, power: int) -> float:
        """NRC_AI 基础伤害公式: (ATK/DEF) * power * 0.9"""
        if def_ <= 0:
            def_ = 1.0
        return (atk / def_) * power * 0.9

    @staticmethod
    def _get_power(skill_meta: Dict[str, Any]) -> int:
        """从技能 meta 中取威力。"""
        dam_para = skill_meta.get("dam_para", [])
        if dam_para:
            return int(dam_para[0])
        return 0

    @staticmethod
    def _get_stat_with_source(pet: Dict[str, Any], stat_name: str) -> Tuple[Optional[int], str]:
        """从抓包数据中提取属性值和来源。来源: 'total', 'calc_bonus', ''。"""
        stats = pet.get("stats", [])
        aliases = _STAT_NAME_ALIASES.get(stat_name, (stat_name,))
        for s in stats:
            if s.get("name") not in aliases:
                continue
            total = s.get("total")
            if total is not None:
                if stat_name != "HP" and total <= 0:
                    break
                return int(total), "total"
            calc = s.get("calc") or 0
            bonus = s.get("bonus") or 0
            if stat_name != "HP" and calc + bonus <= 0:
                break
            return calc + bonus, "calc_bonus"
        return None, ""

    @staticmethod
    def _get_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
        """从抓包数据中提取属性值。"""
        val, _ = DamageCalculator._get_stat_with_source(pet, stat_name)
        return val

    @staticmethod
    def _calc_arena_stat(race_value: int, stat_name: str) -> int:
        """用 NRC_AI 竞技场公式估算平衡后属性值 (IV=0, 性格=坦率).

        公式: HP = 1.7×race + 170, Other = 1.1×race + 60
        参考: references/NRC_AI/src/pokemon_db.py
        """
        if stat_name == "HP":
            return round(1.7 * race_value + 170)
        return round(1.1 * race_value + 60)

    @staticmethod
    def _get_wiki_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
        """从 pet_species 种族值估算竞技场平衡后属性值。

        stat_name 使用小写 key (hp/atk/spa/def/spd/spe) 以匹配 BinData。
        """
        base_id = pet.get("base_id") or pet.get("base_conf_id")
        if not base_id:
            return None
        species_stats = get_pet_species_stats(base_id)
        # 兼容大小写: 先查小写，再查大写
        key = stat_name.lower() if stat_name.isupper() else stat_name
        race = species_stats.get(key) or species_stats.get(stat_name.upper())
        if race:
            return DamageCalculator._calc_arena_stat(int(race), stat_name)
        return None

    @staticmethod
    def _get_base_hit_count(skill_meta: Dict[str, Any]) -> int:
        """从技能 desc 中提取基础连击数（如 '2连击' → 2）。"""
        desc = skill_meta.get("desc", "")
        m = re.search(r'(\d+)连击', desc)
        if m:
            return int(m.group(1))
        return 1
