"""Single-skill damage calculation orchestration."""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.analysis.damage import skill_resolution


def calculate_damage(
    calculator: Any,
    attacker: Dict[str, Any],
    defender: Dict[str, Any],
    skill_meta: Dict[str, Any],
    weather: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    """Run the staged single-skill damage calculation using a calculator facade."""
    base_power = calculator._get_power(skill_meta)
    damage_type = skill_resolution.resolve_damage_type(skill_meta)
    skill_element = skill_resolution.resolve_skill_element(skill_meta)
    runtime_skill = calculator._get_runtime_skill(attacker, skill_meta.get("id"))
    server_runtime = calculator._resolve_server_runtime(runtime_skill, defender)
    power = base_power
    # 服务端同步的 damage_params 在实战样本中并不稳定；先作为候选/解释源，
    # 不默认替代静态技能威力进入公式。
    server_runtime["formula_power_source"] = "skill_config"
    server_runtime["power_used_in_formula"] = False
    calculator._apply_server_power_rule(server_runtime, skill_meta, base_power)
    if not skill_resolution.is_attack_skill(power, damage_type):
        return None
    power = skill_resolution.apply_buff_power_modifiers(
        power,
        attacker,
        skill_element=skill_element,
        skill_name=skill_meta.get("name"),
    )

    # Phase 1: Resolve power
    power, _ = calculator._resolve_power(power, skill_meta, attacker, defender)

    # Phase 2: Resolve combat stats
    stats = calculator._resolve_combat_stats(attacker, defender, damage_type, power)
    if stats is None:
        return None
    effective_atk, effective_def, ability_level, confidence, warnings, stat_sources = stats

    # Phase 3: Compute base damage
    base = calculator._compute_base_damage(power, effective_atk, effective_def, skill_meta, attacker, defender)

    # Phase 4: Apply multipliers (effectiveness, STAB, weather, hooks)
    mult_result = calculator._apply_multipliers(
        base, skill_element, attacker, defender, skill_meta, weather, server_runtime,
    )
    dmg, effectiveness, stab_mult, weather_mult, power_mult, eff_label, is_stab = mult_result

    # Phase 5: Finalize (post_calc hooks, hit count, HP%, energy, result)
    return calculator._finalize_damage(
        dmg, power, ability_level, effective_atk, effective_def,
        effectiveness, stab_mult, weather_mult, power_mult,
        skill_meta, skill_element, attacker, defender,
        damage_type, eff_label, is_stab, confidence, warnings, stat_sources,
        runtime_skill, server_runtime, power,
    )
