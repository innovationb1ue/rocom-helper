"""战术推荐中的技能运行时解析。"""
from __future__ import annotations

import re
from typing import Any, Dict


def skill_runtime(pet: Dict[str, Any], skill_id: Any) -> Dict[str, Any]:
    if skill_id is None:
        return {}
    runtime = pet.get("skill_runtime") or {}
    item = runtime.get(str(skill_id)) or runtime.get(skill_id) or {}
    return item if isinstance(item, dict) else {}


def skill_cd_round(skill: Dict[str, Any], runtime: Dict[str, Any]) -> int:
    for source in (runtime, skill):
        value = source.get("cd_round")
        if isinstance(value, list):
            value = next((item for item in value if item is not None), None)
        if value is not None:
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                return 0
    return 0


def resolve_action_energy_cost(
    skill: Dict[str, Any],
    runtime: Dict[str, Any],
    meta: Dict[str, Any],
) -> int:
    for source, key in (
        (runtime, "cost_energy_result"),
        (skill, "runtime_cost_energy"),
        (runtime, "cost_energy"),
        (runtime, "raw_cost_energy"),
        (skill, "cost_energy"),
    ):
        value = source.get(key)
        if value is not None:
            return int(value)
    costs = meta.get("energy_cost", [0]) if meta else [0]
    return int(costs[0]) if costs else 0


def skill_priority_layer(
    skill: Dict[str, Any],
    runtime: Dict[str, Any],
    meta: Dict[str, Any],
) -> int:
    skill_buff = runtime.get("skill_buff") if isinstance(runtime.get("skill_buff"), dict) else {}
    runtime_priority = skill_buff.get("priority")
    if runtime_priority not in (None, 0):
        try:
            return int(runtime_priority)
        except (TypeError, ValueError):
            pass

    for value in (skill.get("skill_priority"), meta.get("skill_priority") if meta else None):
        if value is not None:
            try:
                return int(value) - 5
            except (TypeError, ValueError):
                break

    desc = str((meta or {}).get("desc") or skill.get("skill_desc") or skill.get("desc") or "")
    match = re.search(r"先手\s*([+-])\s*(\d+)", desc)
    if match:
        layer = int(match.group(2))
        return layer if match.group(1) == "+" else -layer
    if "先手" in desc or "优先" in desc:
        return 1
    if skill.get("priority_display"):
        return 1
    return 0
