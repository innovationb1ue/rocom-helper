"""Damage, skill-cast, heal, and energy action-entry handlers."""
from __future__ import annotations

from typing import Any, Dict

def _handle_damage_entry(self, entry: Dict[str, Any]) -> None:
    target_side = entry.get("damage_target_side")
    if target_side is None:
        self._apply_hp_update(
            None,
            event_kind="damage",
            entry=entry,
            side=entry.get("target_side") or target_side,
            hp_change=entry.get("hp_change"),
            hp_result=entry.get("hp_result"),
            target_hp_after=entry.get("target_hp_after"),
            actual_damage=entry.get("actual_damage") or entry.get("damage"),
            source_hint="damage_entry",
        )
        return
    # damage_target_side is the pet receiving damage — route to its active
    active = self._resolve_pet_for_side(target_side, bind_fallback=True)
    if active is not None:
        self._apply_hp_update(
            active,
            event_kind="damage",
            entry=entry,
            side=target_side,
            target_pet_id=active.get("pet_id"),
            hp_change=entry.get("hp_change"),
            hp_result=entry.get("hp_result"),
            target_hp_after=entry.get("target_hp_after"),
            actual_damage=entry.get("actual_damage") or entry.get("damage"),
            source_hint="damage_entry",
        )
        self._set_active_pet(active)
    else:
        self._apply_hp_update(
            None,
            event_kind="damage",
            entry=entry,
            side=target_side,
            hp_change=entry.get("hp_change"),
            hp_result=entry.get("hp_result"),
            target_hp_after=entry.get("target_hp_after"),
            actual_damage=entry.get("actual_damage") or entry.get("damage"),
            source_hint="damage_entry",
        )

def _handle_skill_cast_entry(self, entry: Dict[str, Any]) -> None:
    actor_side = entry.get("actor_side", "")
    energy_delta = entry.get("energy_delta", 0)
    energy_after = entry.get("energy_after")
    active = self._get_active_for_side(actor_side)
    if active is None:
        return
    skill_id = entry.get("skill_id")
    if skill_id is not None:
        used = active.setdefault("used_skills", [])
        if not any(s.get("skill_id") == skill_id for s in used):
            skill_name = entry.get("skill_name")
            if not skill_name:
                from src.data.loader import get_skill_name
                skill_name = get_skill_name(skill_id)
            if skill_name:
                used.append({"skill_id": skill_id, "skill_name": skill_name})
    if energy_after is not None:
        active["energy"] = min(10, energy_after)
    else:
        active["energy"] = min(10, max(0, active.get("energy", 5) + energy_delta))

def _handle_combo_skill_cast_entry(self, entry: Dict[str, Any]) -> None:
    actor_side = entry.get("actor_side")
    combo_count = entry.get("combo_count")
    if actor_side is not None and combo_count is not None:
        active = self._get_active_for_side(actor_side)
        if active is not None:
            active["combo_bonus"] = combo_count

def _handle_defeat_entry(self, entry: Dict[str, Any]) -> None:
    defeated_side = entry.get("target_side", "")
    active = self._get_active_for_side(defeated_side)
    if active is not None:
        self._apply_hp_update(
            active,
            event_kind="defeat",
            entry=entry,
            side=defeated_side,
            target_pet_id=active.get("pet_id"),
            hp_result=0,
            source_hint="defeat",
        )

def _handle_heal_entry(self, entry: Dict[str, Any]) -> None:
    target_side = entry.get("target_side")
    hp_after = entry.get("hp_result") or entry.get("target_hp_after") or entry.get("hp_after")
    if target_side is None or hp_after is None:
        return
    active = self._get_active_for_side(target_side)
    if active is not None:
        self._apply_hp_update(
            active,
            event_kind="heal",
            entry=entry,
            side=target_side,
            target_pet_id=active.get("pet_id"),
            hp_change=entry.get("hp_change"),
            hp_result=entry.get("hp_result"),
            target_hp_after=hp_after,
            source_hint="heal",
        )

def _handle_energy_entry(self, entry: Dict[str, Any]) -> None:
    target_side = entry.get("target_side") or entry.get("actor_side")
    energy_after = entry.get("energy_after")
    energy_delta = entry.get("energy_delta")
    if target_side is None:
        return
    active = self._get_active_for_side(target_side)
    if active is not None:
        if energy_after is not None:
            active["energy"] = min(10, energy_after)
        elif energy_delta is not None:
            active["energy"] = min(10, max(0, active.get("energy", 5) + energy_delta))
