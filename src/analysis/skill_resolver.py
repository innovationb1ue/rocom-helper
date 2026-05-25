"""Shared skill-list resolution helpers for battle analysis."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.data.loader import get_popular_skills


def skills_from_pool(pet: Dict[str, Any]) -> List[Dict[str, Any]]:
    pool = pet.get("base_skill_pool")
    if not pool:
        return []
    return [{"skill_id": entry.get("skill_id")} for entry in pool if entry.get("skill_id") is not None]


def resolve_equipped_or_pool(pet: Dict[str, Any]) -> List[Dict[str, Any]]:
    equipped = pet.get("equipped_skills") or pet.get("skills") or pet.get("used_skills") or []
    return equipped or skills_from_pool(pet)


def resolve_opponent_skills(opp_active: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    equipped = opp_active.get("equipped_skills") or opp_active.get("skills") or []
    if equipped:
        return equipped, "protocol"

    used = opp_active.get("used_skills") or []
    if used:
        return used, "used"

    pool = skills_from_pool(opp_active)
    if pool:
        return pool, "protocol"

    base_id = opp_active.get("base_id") or opp_active.get("base_conf_id")
    if base_id:
        preset = get_popular_skills(base_id)
        if preset and preset.get("skills"):
            return [{"skill_id": sid} for sid in preset["skills"]], "preset"

    return [], ""
