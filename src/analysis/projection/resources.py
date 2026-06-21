"""能量、技能和连击 entry 状态投影。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.projection.core import active_for_side


def project_energy(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    target_side = entry.get("target_side") or entry.get("actor_side")
    energy_after = entry.get("energy_after")
    energy_delta = entry.get("energy_delta")
    if target_side is None:
        return
    active = active_for_side(state, target_side)
    if active is None:
        return
    if energy_after is not None:
        active["energy"] = min(10, energy_after)
    elif energy_delta is not None:
        active["energy"] = min(10, max(0, active.get("energy", 5) + energy_delta))


def project_combo_skill_cast(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    actor_side = entry.get("actor_side")
    combo_count = entry.get("combo_count")
    if actor_side is None or combo_count is None:
        return
    active = active_for_side(state, actor_side)
    if active is not None:
        active["combo_bonus"] = combo_count


def project_skill_cast(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    actor_side = entry.get("actor_side", "")
    energy_delta = entry.get("energy_delta", 0)
    energy_after = entry.get("energy_after")
    active = active_for_side(state, actor_side)
    if active is None:
        return
    skill_id = entry.get("skill_id")
    if skill_id is not None:
        used = active.setdefault("used_skills", [])
        if not any(skill.get("skill_id") == skill_id for skill in used):
            item = {"skill_id": skill_id}
            if entry.get("skill_name"):
                item["skill_name"] = entry["skill_name"]
            used.append(item)
    if energy_after is not None:
        active["energy"] = min(10, energy_after)
    else:
        active["energy"] = min(10, max(0, active.get("energy", 5) + energy_delta))

