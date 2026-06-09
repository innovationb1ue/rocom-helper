"""服务端同步的伤害参数解析。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.damage import runtime as damage_runtime


def apply_server_power_rule(
    server_runtime: Dict[str, Any],
    skill_meta: Dict[str, Any],
    base_power: int,
    server_power_rules: Dict[str, Dict[str, Any]],
) -> None:
    """按技能白名单把服务器同步威力转换为额外倍率。"""
    skill_id = skill_meta.get("id")
    rule = server_power_rules.get(str(skill_id))
    server_runtime["server_power_applied"] = False
    if not rule:
        server_runtime["server_power_skip_reason"] = "no_rule"
        return

    server_runtime["server_power_rule"] = {
        key: value
        for key, value in rule.items()
        if key in {"enabled", "mode", "requires_matched_target", "keep_restraint", "max_power_ratio"}
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


def resolve_server_runtime(runtime_skill: Dict[str, Any], defender: Dict[str, Any]) -> Dict[str, Any]:
    """按目标读取服务器同步的技能威力参数和克制结果。"""
    if not runtime_skill:
        return {}
    target_keys = damage_runtime.target_keys(defender)
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
    effectiveness = damage_runtime.restraint_to_multiplier(restraint_value)

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
    return {key: value for key, value in out.items() if value is not None}
