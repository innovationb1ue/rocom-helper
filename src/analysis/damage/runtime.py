"""Runtime skill helpers used by DamageCalculator."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def get_runtime_skill(attacker: Dict[str, Any], skill_id: Any) -> Dict[str, Any]:
    if skill_id is None:
        return {}
    runtime = attacker.get("skill_runtime") or {}
    item = runtime.get(str(skill_id)) or runtime.get(skill_id)
    return item if isinstance(item, dict) else {}


def target_keys(pet: Dict[str, Any]) -> List[str]:
    keys: List[str] = []
    for key in ("pet_id", "slot", "side"):
        value = pet.get(key)
        if value is not None:
            keys.append(str(value))
    return keys


def restraint_to_multiplier(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return None
    return {
        -2: 0.25,
        -1: 0.5,
        0: 1.0,
        1: 1.5,
        2: 2.0,
        3: 4.0,
    }.get(ivalue)


def resolve_energy_cost(runtime_skill: Dict[str, Any], skill_meta: Dict[str, Any]) -> Tuple[int, str]:
    for key, source in (
        ("cost_energy_result", "skill_sync.cost_energy_result"),
        ("cost_energy", "pet_skill.cost_energy"),
        ("raw_cost_energy", "pet_skill.raw_cost_energy"),
    ):
        if runtime_skill.get(key) is not None:
            return int(runtime_skill[key]), source
    energy_costs = skill_meta.get("energy_cost", [0])
    return (int(energy_costs[0]) if energy_costs else 0), "skill_config"


def runtime_sources(runtime_skill: Dict[str, Any], server_runtime: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "has_damage_params": bool(runtime_skill.get("damage_params_by_pet")),
        "has_restraint_types": bool(runtime_skill.get("restraint_types_by_pet")),
        "has_set_cost_info": bool(runtime_skill.get("set_cost_info")),
        "has_cr_damage_params": bool(runtime_skill.get("cr_damage_params")),
        "has_extra_damage_type": bool(runtime_skill.get("extra_damage_type")),
        "has_skill_buff": bool(runtime_skill.get("skill_buff")),
        "matched_target_key": server_runtime.get("matched_target_key"),
        "runtime_power": server_runtime.get("power") or runtime_skill.get("damage_param_result"),
        "power_used_in_formula": bool(server_runtime.get("power_used_in_formula")),
        "server_power_applied": bool(server_runtime.get("server_power_applied")),
        "server_power_skip_reason": server_runtime.get("server_power_skip_reason"),
    }
