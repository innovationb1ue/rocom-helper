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
import copy
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from src.data.loader import (
    get_buff_derived_stat_modifiers,
    get_buff_hit_count_modifiers,
    get_buff_power_modifiers,
    get_buff_stat_modifiers,
    get_skill_meta,
    get_skill_name,
    get_pet_species_stats,
    get_nature_stat_modifiers,
    get_weather_damage_mult,
)
from src.game.type_chart import TypeChart
from src.game.stats import calc_pvp_template_stat
from src.analysis.constants import SDT_TO_TYPE
from src.analysis.damage import runtime as damage_runtime

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
_SPECIAL_FIXED_LIGHT_SKILLS: Dict[int, str] = {}


class DamageCalculator:
    def __init__(
        self,
        type_chart: Optional[TypeChart] = None,
        *,
        server_power_rules: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.chart = type_chart or TypeChart()
        self._hooks: Dict[HookStage, List[DamageHook]] = {
            "pre_power": [],
            "post_base": [],
            "pre_final": [],
            "post_calc": [],
        }
        self._server_power_rules: Dict[str, Dict[str, Any]] = {}
        self.set_server_power_rules(server_power_rules or {})

    def set_server_power_rules(self, rules: Dict[str, Any]) -> None:
        """设置按技能启用的服务器威力规则。"""
        raw = rules.get("skills", rules) if isinstance(rules, dict) else {}
        self._server_power_rules = {
            str(skill_id): dict(rule)
            for skill_id, rule in raw.items()
            if isinstance(rule, dict)
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

    def _apply_server_power_rule(
        self,
        server_runtime: Dict[str, Any],
        skill_meta: Dict[str, Any],
        base_power: int,
    ) -> None:
        """按技能白名单把服务器同步威力转换为额外倍率。"""
        skill_id = skill_meta.get("id")
        rule = self._server_power_rules.get(str(skill_id))
        server_runtime["server_power_applied"] = False
        if not rule:
            server_runtime["server_power_skip_reason"] = "no_rule"
            return

        server_runtime["server_power_rule"] = {
            k: v for k, v in rule.items()
            if k in {"enabled", "mode", "requires_matched_target", "keep_restraint", "max_power_ratio"}
        }
        if not rule.get("enabled", True):
            server_runtime["server_power_skip_reason"] = "disabled"
            return
        if rule.get("mode") != "multiplier_over_base_power":
            server_runtime["server_power_skip_reason"] = "unsupported_mode"
            return
        if (
            rule.get("requires_matched_target", True)
            and server_runtime.get("has_damage_params")
            and not server_runtime.get("matched_target_key")
        ):
            server_runtime["server_power_skip_reason"] = "target_unmatched"
            return
        if server_runtime.get("power_source") != "server_damage_params":
            server_runtime["server_power_skip_reason"] = "no_server_damage_params"
            return
        runtime_power = server_runtime.get("power")
        if base_power <= 0 or runtime_power is None:
            server_runtime["server_power_skip_reason"] = "missing_power"
            return
        try:
            multiplier = float(runtime_power) / float(base_power)
        except (TypeError, ValueError, ZeroDivisionError):
            server_runtime["server_power_skip_reason"] = "invalid_power"
            return
        if multiplier <= 0:
            server_runtime["server_power_skip_reason"] = "invalid_ratio"
            return
        max_ratio = float(rule.get("max_power_ratio", 5.0) or 5.0)
        if multiplier > max_ratio:
            server_runtime["server_power_multiplier"] = multiplier
            server_runtime["server_power_skip_reason"] = "ratio_exceeded"
            return
        server_runtime["server_power_multiplier"] = multiplier
        server_runtime["server_power_applied"] = True
        server_runtime["server_power_skip_reason"] = None

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
        base_power = self._get_power(skill_meta)
        damage_type = skill_meta.get("damage_type", 0)
        raw_dam_type = skill_meta.get("skill_dam_type", 0)
        skill_element = SDT_TO_TYPE.get(raw_dam_type, raw_dam_type)
        runtime_skill = self._get_runtime_skill(attacker, skill_meta.get("id"))
        server_runtime = self._resolve_server_runtime(runtime_skill, defender)
        power = base_power
        # 服务端同步的 damage_params 在实战样本中并不稳定；先作为候选/解释源，
        # 不默认替代静态技能威力进入公式。
        server_runtime["formula_power_source"] = "skill_config"
        server_runtime["power_used_in_formula"] = False
        self._apply_server_power_rule(server_runtime, skill_meta, base_power)
        if power <= 0 or damage_type not in (2, 3):
            return None
        buff_power_modifiers = get_buff_power_modifiers(
            attacker.get("buffs", []),
            skill_element=skill_element,
            skill_name=skill_meta.get("name"),
        )
        if buff_power_modifiers.get("flat"):
            power = max(1, power + int(buff_power_modifiers["flat"]))

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
        mult_result = self._apply_multipliers(
            base, skill_element, attacker, defender, skill_meta, weather, server_runtime,
        )
        dmg, effectiveness, stab_mult, weather_mult, power_mult, eff_label, is_stab = mult_result

        # Phase 5: Finalize (post_calc hooks, hit count, HP%, energy, result)
        return self._finalize_damage(
            dmg, power, ability_level, effective_atk, effective_def,
            effectiveness, stab_mult, weather_mult, power_mult,
            skill_meta, skill_element, attacker, defender,
            damage_type, eff_label, is_stab, confidence, warnings, stat_sources,
            runtime_skill, server_runtime, power,
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
            base_atk = self._get_pvp_template_stat(attacker, atk_name)
            atk_source = "pvp_template" if base_atk is not None else ""
        if base_def is None:
            base_def = self._get_pvp_template_stat(defender, def_name)
            def_source = "pvp_template" if base_def is not None else ""
        if base_atk is None:
            base_atk = self._get_wiki_stat(attacker, atk_name)
            atk_source = "wiki" if base_atk is not None else ""
        if base_def is None:
            base_def = self._get_wiki_stat(defender, def_name)
            def_source = "wiki" if base_def is not None else ""

        if base_atk is None or base_def is None:
            return None

        # 置信度分级: high(total 存在) / medium(calc+bonus 或 PvP 模板) / low(wiki 估算)
        sources = {atk_source, def_source}
        if "wiki" in sources:
            confidence = "low"
            if atk_source == "wiki":
                warnings.append("攻击属性来自 wiki 估算")
            if def_source == "wiki":
                warnings.append("防御属性来自 wiki 估算")
        elif "calc_bonus" in sources or "pvp_template" in sources:
            confidence = "medium"
            if atk_source == "calc_bonus":
                warnings.append("攻击属性来自 calc+bonus 估算")
            if def_source == "calc_bonus":
                warnings.append("防御属性来自 calc+bonus 估算")
            if atk_source == "pvp_template":
                warnings.append("攻击属性来自 PvP 通用模板估算")
            if def_source == "pvp_template":
                warnings.append("防御属性来自 PvP 通用模板估算")

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
        weather: Optional[Dict], server_runtime: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, float, float, float, float, str, bool]:
        """阶段 3: 属性克制、STAB、天气、pre_final hook。"""
        defender_types = defender.get("types", [])
        local_effectiveness = self.chart.get_multiplier(skill_element, defender_types)
        server_runtime = server_runtime or {}
        server_effectiveness = server_runtime.get("effectiveness")
        display_effectiveness = server_effectiveness if server_effectiveness is not None else local_effectiveness
        # damage_params 已按目标给出威力参数，进入公式后不再重复乘克制。
        calc_effectiveness = (
            1.0
            if server_runtime.get("power_source") == "server_damage_params"
            and server_runtime.get("power_used_in_formula")
            else display_effectiveness
        )
        server_runtime["local_effectiveness"] = local_effectiveness
        server_runtime["display_effectiveness"] = display_effectiveness
        server_runtime["calc_effectiveness"] = calc_effectiveness
        eff_label = self.chart.get_effectiveness_label(display_effectiveness)

        attacker_types = attacker.get("types", [])
        is_stab = skill_element in attacker_types
        stab_mult = _STAB_MULTIPLIER if is_stab else 1.0

        weather_mult = get_weather_damage_mult(weather, skill_element)
        power_mult = 1.0

        ctx = self._run_hooks("pre_final", {
            "base_damage": base,
            "effectiveness": calc_effectiveness,
            "stab_mult": stab_mult,
            "weather_mult": weather_mult,
            "power_mult": power_mult,
            "skill_meta": skill_meta,
            "attacker": attacker,
            "defender": defender,
        })
        base = ctx["base_damage"]
        calc_effectiveness = ctx["effectiveness"]
        stab_mult = ctx["stab_mult"]
        weather_mult = ctx.get("weather_mult", weather_mult)
        power_mult = ctx.get("power_mult", power_mult)
        if server_runtime.get("server_power_applied"):
            power_mult *= float(server_runtime.get("server_power_multiplier") or 1.0)
        if server_runtime.get("effectiveness_source") != "server_restraint_types":
            display_effectiveness = calc_effectiveness
            eff_label = self.chart.get_effectiveness_label(display_effectiveness)
        server_runtime["display_effectiveness"] = display_effectiveness
        server_runtime["calc_effectiveness"] = calc_effectiveness

        dmg = max(1, int(base * calc_effectiveness * stab_mult * weather_mult * power_mult))
        return dmg, display_effectiveness, stab_mult, weather_mult, power_mult, eff_label, is_stab

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
        runtime_skill: Optional[Dict[str, Any]] = None,
        server_runtime: Optional[Dict[str, Any]] = None,
        final_power: Optional[int] = None,
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
        buff_hit_modifiers = get_buff_hit_count_modifiers(
            attacker.get("buffs", []),
            skill_element=skill_element,
            skill_name=skill_meta.get("name"),
            base_hit_count=hit_count,
        )
        if buff_hit_modifiers.get("flat"):
            hit_count = max(1, int(hit_count + buff_hit_modifiers["flat"]))
        special_mode = _SPECIAL_FIXED_LIGHT_SKILLS.get(skill_meta.get("id"))
        total_damage = dmg * hit_count

        defender_max_hp = defender.get("max_hp") or defender.get("current_hp") or 1
        defender_cur_hp = defender.get("current_hp") or 0
        pct = total_damage / defender_max_hp
        can_ko = total_damage >= defender_cur_hp

        runtime_skill = runtime_skill or self._get_runtime_skill(attacker, skill_meta.get("id"))
        server_runtime = server_runtime or self._resolve_server_runtime(runtime_skill, defender)
        attacker_buff_modifiers = get_buff_stat_modifiers(attacker.get("buffs", []))
        attacker_derived_modifiers = get_buff_derived_stat_modifiers(attacker.get("buffs", []))
        defender_buff_modifiers = get_buff_stat_modifiers(defender.get("buffs", []))
        attacker_derived_buffs = self._collect_derived_buffs(attacker.get("buffs", []))
        reflect_candidate_effects = copy.deepcopy(attacker.get("reflect_candidate_effects") or [])
        reflect_confirmed_effects = copy.deepcopy(attacker.get("reflect_confirmed_effects") or [])
        buff_power_modifiers = get_buff_power_modifiers(
            attacker.get("buffs", []),
            skill_element=skill_element,
            skill_name=skill_meta.get("name"),
        )
        reflect_buff_applied = any(
            buff.get("id") == 20890020 and (
                buff.get("derived_buffs")
                or buff.get("modifiers")
                or get_buff_derived_stat_modifiers([buff])
            )
            for buff in attacker.get("buffs", []) or []
            if isinstance(buff, dict)
        )
        runtime_power = server_runtime.get("power") or runtime_skill.get("damage_param_result")
        energy_cost, energy_cost_source = self._resolve_energy_cost(runtime_skill, skill_meta)
        if energy_cost > 0:
            attacker_energy = attacker.get("energy", 10)
            if attacker_energy < energy_cost:
                warnings.append(f"能量不足 (需要{energy_cost}, 当前{attacker_energy})")

        effective_power = int(power * stab_mult)
        runtime_sources = self._runtime_sources(runtime_skill, server_runtime)
        breakdown = {
            "base_power": self._get_power(skill_meta),
            "final_power": final_power if final_power is not None else power,
            "power_source": server_runtime.get("formula_power_source", "skill_config"),
            "energy_cost_source": energy_cost_source,
            "effectiveness_source": server_runtime.get("effectiveness_source", "type_chart"),
            "effective_power": effective_power,
            "runtime_power": runtime_power,
            "damage_param_result": runtime_power,
            "runtime_skill": runtime_skill or None,
            "server_runtime": server_runtime or None,
            "runtime_sources": runtime_sources,
            "skill_element": skill_element,
            "server_power_rule": server_runtime.get("server_power_rule"),
            "server_power_multiplier": server_runtime.get("server_power_multiplier"),
            "server_power_applied": bool(server_runtime.get("server_power_applied")),
            "server_power_skip_reason": server_runtime.get("server_power_skip_reason"),
            "ability_level": round(ability_level, 3),
            "attacker_buff_modifiers": attacker_buff_modifiers,
            "attacker_derived_buff_modifiers": attacker_derived_modifiers,
            "attacker_derived_buffs": attacker_derived_buffs,
            "reflect_candidate_effects": reflect_candidate_effects,
            "reflect_confirmed_effects": reflect_confirmed_effects,
            "reflect_buff_applied": reflect_buff_applied,
            "special_damage_rule": (
                {
                    "mode": special_mode,
                    "element": skill_element,
                    "source": "config_missing",
                    "applied": False,
                }
                if special_mode else None
            ),
            "buff_power_modifiers": buff_power_modifiers,
            "buff_hit_count_modifiers": buff_hit_modifiers,
            "defender_buff_modifiers": defender_buff_modifiers,
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

    @staticmethod
    def _collect_derived_buffs(buff_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        derived: List[Dict[str, Any]] = []
        for buff in buff_list or []:
            if not isinstance(buff, dict):
                continue
            parent = {
                "id": buff.get("id"),
                "name": buff.get("name"),
            }
            for item in buff.get("derived_buffs") or []:
                if isinstance(item, dict):
                    child = dict(item)
                else:
                    child = {"id": item}
                child.setdefault("parent_buff_id", parent.get("id"))
                child.setdefault("parent_buff_name", parent.get("name"))
                derived.append({k: v for k, v in child.items() if v is not None})
        return derived

    @staticmethod
    def _runtime_sources(runtime_skill: Dict[str, Any], server_runtime: Dict[str, Any]) -> Dict[str, Any]:
        """汇总服务端同步运行时字段，供预测解释和审计使用。"""
        return damage_runtime.runtime_sources(runtime_skill, server_runtime)

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
    def _get_runtime_skill(attacker: Dict[str, Any], skill_id: Any) -> Dict[str, Any]:
        """从状态机的 skill_runtime 中读取当前战斗里的技能同步参数。"""
        return damage_runtime.get_runtime_skill(attacker, skill_id)

    @staticmethod
    def _target_keys(pet: Dict[str, Any]) -> List[str]:
        return damage_runtime.target_keys(pet)

    @staticmethod
    def _restraint_to_multiplier(value: Any) -> Optional[float]:
        return damage_runtime.restraint_to_multiplier(value)

    def _resolve_server_runtime(self, runtime_skill: Dict[str, Any], defender: Dict[str, Any]) -> Dict[str, Any]:
        """按目标读取服务器同步的技能威力参数和克制结果。"""
        if not runtime_skill:
            return {}
        target_keys = self._target_keys(defender)
        damage_by_pet = runtime_skill.get("damage_params_by_pet") or {}
        restraint_by_pet = runtime_skill.get("restraint_types_by_pet") or {}

        runtime_power = None
        power_source = "skill_config"
        matched_damage_key = None
        for key in target_keys:
            if damage_by_pet.get(key) is not None:
                runtime_power = damage_by_pet[key]
                power_source = "server_damage_params"
                matched_damage_key = key
                break
        if runtime_power is None and defender.get("pet_id") == 20000000 and len(damage_by_pet) == 1:
            # 对手隐藏身份时状态机可能没有真实 pet_id；服务器此刻只给一个目标威力，可作为当前目标。
            matched_damage_key, runtime_power = next(iter(damage_by_pet.items()))
            power_source = "server_damage_params"
        if runtime_power is None and runtime_skill.get("damage_param_result") is not None:
            runtime_power = runtime_skill["damage_param_result"]
            power_source = "server_damage_param_result"

        restraint_value = None
        for key in target_keys:
            if restraint_by_pet.get(key) is not None:
                restraint_value = restraint_by_pet[key]
                break
        if restraint_value is None and matched_damage_key is not None and restraint_by_pet.get(str(matched_damage_key)) is not None:
            restraint_value = restraint_by_pet[str(matched_damage_key)]
        effectiveness = self._restraint_to_multiplier(restraint_value)

        out: Dict[str, Any] = {
            "runtime_skill": runtime_skill,
            "power": runtime_power,
            "power_source": power_source,
            "target_keys": target_keys,
            "matched_target_key": matched_damage_key,
            "has_damage_params": bool(damage_by_pet),
        }
        if effectiveness is not None:
            out["effectiveness"] = effectiveness
            out["restraint_type"] = restraint_value
            out["effectiveness_source"] = "server_restraint_types"
        else:
            out["effectiveness_source"] = "type_chart"
        return {k: v for k, v in out.items() if v is not None}

    @staticmethod
    def _resolve_energy_cost(runtime_skill: Dict[str, Any], skill_meta: Dict[str, Any]) -> Tuple[int, str]:
        return damage_runtime.resolve_energy_cost(runtime_skill, skill_meta)

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
        return calc_pvp_template_stat(race_value, stat_name)

    @staticmethod
    def _nature_modifiers(pet: Dict[str, Any]) -> Dict[str, float]:
        for key in ("nature_stat_modifiers", "nature_modifiers"):
            mods = pet.get(key)
            if isinstance(mods, dict):
                return {str(k).lower(): float(v) for k, v in mods.items()}
        nature_id = pet.get("nature_id") or pet.get("nature")
        if nature_id is not None:
            return get_nature_stat_modifiers(nature_id)
        return {}

    @staticmethod
    def _get_pvp_template_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
        """从 pet_species 种族值按 PvP 通用模板估算平衡后属性值。

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
            nature_mod = DamageCalculator._nature_modifiers(pet).get(key, 0.0)
            return calc_pvp_template_stat(int(race), stat_name, nature_mod)
        return None

    @staticmethod
    def _get_wiki_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
        """旧兜底接口。当前没有独立 wiki 属性源，保留为兼容入口。"""
        return None

    @staticmethod
    def _get_base_hit_count(skill_meta: Dict[str, Any]) -> int:
        """从技能 desc 中提取基础连击数（如 '2连击' → 2）。"""
        desc = skill_meta.get("desc", "")
        m = re.search(r'(\d+)连击', desc)
        if m:
            return int(m.group(1))
        return 1
