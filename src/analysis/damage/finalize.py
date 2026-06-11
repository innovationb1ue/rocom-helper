"""伤害计算最终结果构造。"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.analysis.damage import combat_stats
from src.analysis.damage import runtime as damage_runtime
from src.analysis.damage import server_runtime as damage_server_runtime
from src.analysis.damage.hook_pipeline import HookStage
from src.analysis.damage.result import (
    DamageResult,
    base_hit_count,
    collect_derived_buffs,
    skill_power,
)
from src.data.loader import (
    get_buff_derived_stat_modifiers,
    get_buff_hit_count_modifiers,
    get_buff_power_modifiers,
)

RunHooks = Callable[[HookStage, Dict[str, Any]], Dict[str, Any]]
TypeName = Callable[[int], str]


@dataclass
class DamageFinalizeInput:
    dmg: int
    power: int
    ability_level: float
    effective_atk: float
    effective_def: float
    effectiveness: float
    stab_mult: float
    weather_mult: float
    power_mult: float
    skill_meta: Dict[str, Any]
    skill_element: int
    attacker: Dict[str, Any]
    defender: Dict[str, Any]
    damage_type: int
    eff_label: str
    is_stab: bool
    confidence: str
    warnings: List[str]
    stat_sources: Dict[str, str]
    runtime_skill: Optional[Dict[str, Any]] = None
    server_runtime: Optional[Dict[str, Any]] = None
    final_power: Optional[int] = None
    special_fixed_light_skills: Optional[Dict[int, str]] = None


def finalize_damage_result(
    data: DamageFinalizeInput,
    *,
    run_hooks: RunHooks,
    type_name: TypeName,
) -> DamageResult:
    """执行 post_calc 阶段并构造 DamageResult。"""
    ctx = run_hooks("post_calc", {
        "min_damage": data.dmg,
        "max_damage": data.dmg,
        "hit_count": base_hit_count(data.skill_meta),
        "effectiveness": data.effectiveness,
        "stab_mult": data.stab_mult,
        "skill_meta": data.skill_meta,
        "attacker": data.attacker,
        "defender": data.defender,
    })
    dmg = ctx["min_damage"]

    hit_count = ctx.get("hit_count", 1)
    runtime_skill = data.runtime_skill or damage_runtime.get_runtime_skill(
        data.attacker,
        data.skill_meta.get("id"),
    )
    server_runtime = data.server_runtime or damage_server_runtime.resolve_server_runtime(
        runtime_skill,
        data.defender,
    )
    buff_hit_modifiers = get_buff_hit_count_modifiers(
        data.attacker.get("buffs", []),
        skill_element=data.skill_element,
        skill_name=data.skill_meta.get("name"),
        base_hit_count=hit_count,
        allow_reflect_derived_hit=server_runtime.get("server_power_skip_reason") != "target_unmatched",
    )
    if buff_hit_modifiers.get("flat"):
        hit_count = max(1, int(hit_count + buff_hit_modifiers["flat"]))
    special_mode = (data.special_fixed_light_skills or {}).get(data.skill_meta.get("id"))
    total_damage = dmg * hit_count

    defender_max_hp = data.defender.get("max_hp") or data.defender.get("current_hp") or 1
    defender_cur_hp = data.defender.get("current_hp") or 0
    pct = total_damage / defender_max_hp
    can_ko = total_damage >= defender_cur_hp

    energy_cost, energy_cost_source = damage_runtime.resolve_energy_cost(runtime_skill, data.skill_meta)
    warnings = list(data.warnings)
    if energy_cost > 0:
        attacker_energy = data.attacker.get("energy", 10)
        if attacker_energy < energy_cost:
            warnings.append(f"能量不足 (需要{energy_cost}, 当前{attacker_energy})")

    effective_power = int(data.power * data.stab_mult)
    breakdown = build_damage_breakdown(
        data,
        runtime_skill=runtime_skill,
        server_runtime=server_runtime,
        energy_cost_source=energy_cost_source,
        effective_power=effective_power,
        hit_count=hit_count,
        buff_hit_modifiers=buff_hit_modifiers,
        special_mode=special_mode,
        defender_cur_hp=defender_cur_hp,
        defender_max_hp=defender_max_hp,
    )

    return DamageResult(
        skill_id=data.skill_meta.get("id", 0),
        skill_name=data.skill_meta.get("name", "?"),
        power=skill_power(data.skill_meta),
        effective_power=effective_power,
        damage_type=data.damage_type,
        skill_element=data.skill_element,
        skill_element_name=type_name(data.skill_element) if data.skill_element else "无属性",
        effectiveness=data.effectiveness,
        effectiveness_label=data.eff_label,
        is_stab=data.is_stab,
        expected_damage=dmg,
        pct_hp=round(pct, 3),
        can_ko=can_ko,
        energy_cost=energy_cost,
        confidence=data.confidence,
        hit_count=hit_count,
        power_mult=data.power_mult,
        weather_mult=data.weather_mult,
        damage_breakdown=breakdown,
        warnings=warnings,
    )


def build_damage_breakdown(
    data: DamageFinalizeInput,
    *,
    runtime_skill: Dict[str, Any],
    server_runtime: Dict[str, Any],
    energy_cost_source: str,
    effective_power: int,
    hit_count: int,
    buff_hit_modifiers: Dict[str, Any],
    special_mode: Optional[str],
    defender_cur_hp: int,
    defender_max_hp: int,
) -> Dict[str, Any]:
    """构造用于解释、审计和前端展示的 damage_breakdown。"""
    runtime_power = server_runtime.get("power") or runtime_skill.get("damage_param_result")
    return {
        "base_power": skill_power(data.skill_meta),
        "final_power": data.final_power if data.final_power is not None else data.power,
        "power_source": server_runtime.get("formula_power_source", "skill_config"),
        "energy_cost_source": energy_cost_source,
        "effectiveness_source": server_runtime.get("effectiveness_source", "type_chart"),
        "effective_power": effective_power,
        "runtime_power": runtime_power,
        "damage_param_result": runtime_power,
        "runtime_skill": runtime_skill or None,
        "server_runtime": server_runtime or None,
        "runtime_sources": damage_runtime.runtime_sources(runtime_skill, server_runtime),
        "skill_element": data.skill_element,
        "server_power_rule": server_runtime.get("server_power_rule"),
        "server_power_multiplier": server_runtime.get("server_power_multiplier"),
        "server_power_applied": bool(server_runtime.get("server_power_applied")),
        "server_power_skip_reason": server_runtime.get("server_power_skip_reason"),
        "ability_level": round(data.ability_level, 3),
        "attacker_buff_modifiers": combat_stats.resolve_stat_buff_modifiers(data.attacker.get("buffs", [])),
        "attacker_derived_buff_modifiers": get_buff_derived_stat_modifiers(data.attacker.get("buffs", [])),
        "attacker_derived_buffs": collect_derived_buffs(data.attacker.get("buffs", [])),
        "reflect_candidate_effects": copy.deepcopy(data.attacker.get("reflect_candidate_effects") or []),
        "reflect_confirmed_effects": copy.deepcopy(data.attacker.get("reflect_confirmed_effects") or []),
        "reflect_buff_applied": reflect_buff_applied(data.attacker.get("buffs", [])),
        "special_damage_rule": (
            {
                "mode": special_mode,
                "element": data.skill_element,
                "source": "config_missing",
                "applied": False,
            }
            if special_mode else None
        ),
        "buff_power_modifiers": get_buff_power_modifiers(
            data.attacker.get("buffs", []),
            skill_element=data.skill_element,
            skill_name=data.skill_meta.get("name"),
        ),
        "buff_hit_count_modifiers": buff_hit_modifiers,
        "defender_buff_modifiers": combat_stats.resolve_stat_buff_modifiers(data.defender.get("buffs", [])),
        "atk": int(data.effective_atk),
        "def_": int(data.effective_def),
        "effectiveness": data.effectiveness,
        "stab": data.stab_mult,
        "weather_mult": data.weather_mult,
        "power_mult": data.power_mult,
        "hit_count": hit_count,
        "stat_sources": data.stat_sources,
        "defender_current_hp": defender_cur_hp,
        "defender_max_hp": defender_max_hp,
    }


def reflect_buff_applied(buff_list: List[Dict[str, Any]]) -> bool:
    """判断折射 buff 是否已真正携带可用于伤害计算的派生修正。"""
    return any(
        buff.get("id") == 20890020 and (
            buff.get("derived_buffs")
            or buff.get("modifiers")
            or get_buff_derived_stat_modifiers([buff])
        )
        for buff in buff_list or []
        if isinstance(buff, dict)
    )
