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
    get_weather_damage_mult,
    get_wiki_pet_stats,
)
from src.game.type_chart import TypeChart
from src.protocol.proto_core import SDT_TO_TYPE

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
    min_damage: int
    max_damage: int
    pct_hp_range: Tuple[float, float]
    can_ko: bool
    energy_cost: int
    confidence: str  # "high" / "medium"
    hit_count: int = 1
    total_min_damage: int = 0
    total_max_damage: int = 0
    power_mult: float = 1.0
    weather_mult: float = 1.0
    damage_breakdown: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 属性名到 stat name 的映射
_ATK_STAT = {2: "ATK", 3: "SPA"}  # damage_type → 攻击属性
_DEF_STAT = {2: "DEF", 3: "SPD"}  # damage_type → 防御属性

# STAB 倍率
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

        # SDT → type chart ID 转换
        raw_dam_type = skill_meta.get("skill_dam_type", 0)
        skill_element = SDT_TO_TYPE.get(raw_dam_type, raw_dam_type)

        confidence = "high"
        warnings: List[str] = []

        # === 阶段 1/4: pre_power — 可修正威力 ===
        ctx = self._run_hooks("pre_power", {
            "power": power,
            "skill_meta": skill_meta,
            "attacker": attacker,
            "defender": defender,
        })
        power = ctx["power"]

        # 获取基础攻防属性
        atk_name = _ATK_STAT[damage_type]
        def_name = _DEF_STAT[damage_type]
        base_atk = self._get_stat(attacker, atk_name)
        base_def = self._get_stat(defender, def_name)

        # 回退到 wiki 数据
        if base_atk is None:
            base_atk = self._get_wiki_stat(attacker, atk_name)
            if base_atk is not None:
                confidence = "medium"
                warnings.append("攻击属性来自 wiki 估算")
        if base_def is None:
            base_def = self._get_wiki_stat(defender, def_name)
            if base_def is not None:
                confidence = "medium"
                warnings.append("防御属性来自 wiki 估算")

        if base_atk is None or base_def is None:
            return None

        # NRC_AI 能力等级计算
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

        # 基础伤害: NRC_AI 公式
        base = self._base_damage(effective_atk, effective_def, power)

        # === 阶段 2/4: post_base — 可修正基础伤害 ===
        ctx = self._run_hooks("post_base", {
            "base_damage": base,
            "power": power,
            "atk_val": effective_atk,
            "def_val": effective_def,
            "skill_meta": skill_meta,
            "attacker": attacker,
            "defender": defender,
        })
        base = ctx["base_damage"]

        # 属性克制 (使用 type chart ID)
        defender_types = defender.get("types", [])
        effectiveness = self.chart.get_multiplier(skill_element, defender_types)
        eff_label = self.chart.get_effectiveness_label(effectiveness)

        # STAB (使用 type chart ID)
        attacker_types = attacker.get("types", [])
        is_stab = skill_element in attacker_types
        stab_mult = _STAB_MULTIPLIER if is_stab else 1.0

        # 天气修正
        weather_mult = get_weather_damage_mult(weather, skill_element)

        # 独立威力乘法层 (默认 1.0, 可由 hook 修改)
        power_mult = 1.0

        # === 阶段 3/4: pre_final — 可修正属性克制/STAB/天气/威力乘法 ===
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

        # 最终伤害 (确定性, 无随机因子)
        dmg = max(1, int(base * effectiveness * stab_mult * weather_mult * power_mult))

        # === 阶段 4/4: post_calc — 可修正最终伤害/连击数 ===
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

        # 连击信息
        hit_count = ctx.get("hit_count", 1)
        total_damage = dmg * hit_count

        # HP 百分比
        defender_max_hp = defender.get("max_hp") or defender.get("current_hp") or 1
        defender_cur_hp = defender.get("current_hp") or 0
        pct = total_damage / defender_max_hp
        can_ko = total_damage >= defender_cur_hp

        # 能耗
        energy_costs = skill_meta.get("energy_cost", [0])
        energy_cost = energy_costs[0] if energy_costs else 0
        if energy_cost > 0:
            attacker_energy = attacker.get("energy", 10)
            if attacker_energy < energy_cost:
                warnings.append(f"能量不足 (需要{energy_cost}, 当前{attacker_energy})")

        # 有效威力 = 基础威力 × 本系修正 (游戏中的显示方式)
        effective_power = int(power * stab_mult)

        # 伤害分解
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
            min_damage=dmg,
            max_damage=dmg,
            pct_hp_range=(round(pct, 3), round(pct, 3)),
            can_ko=can_ko,
            energy_cost=energy_cost,
            confidence=confidence,
            hit_count=hit_count,
            total_min_damage=total_damage,
            total_max_damage=total_damage,
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
    def _get_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
        """从抓包数据中提取属性值。"""
        stats = pet.get("stats", [])
        for s in stats:
            if s.get("name") == stat_name:
                total = s.get("total")
                if total is not None:
                    return int(total)
                calc = s.get("calc") or 0
                bonus = s.get("bonus") or 0
                return calc + bonus
        return None

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
        """从 wiki 种族值估算竞技场平衡后属性值。"""
        name = pet.get("name")
        if not name:
            return None
        wiki_stats = get_wiki_pet_stats(name)
        if wiki_stats and stat_name in wiki_stats:
            race = int(wiki_stats[stat_name])
            return DamageCalculator._calc_arena_stat(race, stat_name)
        return None

    @staticmethod
    def _get_base_hit_count(skill_meta: Dict[str, Any]) -> int:
        """从技能 desc 中提取基础连击数（如 '2连击' → 2）。"""
        desc = skill_meta.get("desc", "")
        m = re.search(r'(\d+)连击', desc)
        if m:
            return int(m.group(1))
        return 1
