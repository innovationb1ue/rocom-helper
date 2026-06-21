"""Buff/effect entry 状态投影。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.battle_state import POISON_BUFF_IDS
from src.analysis.projection.core import active_for_side
from src.data.loader import enrich_buff_modifiers


def project_effect_apply(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    target_side = entry.get("target_side")
    effect_id = entry.get("effect_id")
    if target_side is None or effect_id is None:
        return
    active = active_for_side(state, target_side)
    if active is None:
        return
    buffs = active.setdefault("buffs", [])
    stage = entry.get("effect_stage")
    effect_name = entry.get("effect_name")
    if stage == 3:
        active["buffs"] = [buff for buff in buffs if buff.get("id") != effect_id]
        return
    existing = next((buff for buff in buffs if buff["id"] == effect_id), None)
    if existing:
        if stage is not None:
            existing["stage"] = stage
            existing.update(enrich_buff_modifiers(existing))
        existing["turns_applied"] = existing.get("turns_applied", 0) + 1
    else:
        buffs.append(enrich_buff_modifiers({
            "id": effect_id,
            "name": effect_name or str(effect_id),
            "stage": stage,
            "source_skill": _source_skill_name(entry),
            "turns_applied": 1,
        }))
    if effect_id in POISON_BUFF_IDS:
        active["poison_stacks"] = stage if stage is not None else active.get("poison_stacks", 0) + 1


def project_effect_stage(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    actor_side = entry.get("actor_side")
    effect_id = entry.get("effect_id")
    new_stage = entry.get("effect_stage")
    if actor_side is None:
        return
    active = active_for_side(state, actor_side)
    if active is None:
        return
    buffs = active.get("buffs", [])
    if new_stage == 3:
        active["buffs"] = [buff for buff in buffs if buff.get("id") != effect_id]
        return
    existing = next((buff for buff in buffs if buff.get("id") == effect_id), None)
    if existing and new_stage is not None:
        existing["stage"] = new_stage
        existing.update(enrich_buff_modifiers(existing))


def _source_skill_name(entry: Dict[str, Any]) -> Any:
    related_skills = entry.get("related_skills") or []
    if not related_skills:
        return None
    return related_skills[0].get("skill_name")

