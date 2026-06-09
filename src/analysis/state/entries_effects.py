"""Buff/effect action-entry handlers."""
from __future__ import annotations

import copy
from typing import Any, Dict

from src.analysis.reflect_effects import (
    REFLECT_BUFF_ID,
    REFLECT_BUFFBASE_ID,
    build_reflect_candidate_effects,
    reflect_effect_for_buff,
)
from src.data.loader import enrich_buff_modifiers

POISON_BUFF_IDS = {20070010}
MAX_REFLECT_CANDIDATES = 120

def _handle_effect_apply_entry(self, entry: Dict[str, Any]) -> None:
    target_side = entry.get("target_side")
    effect_id = entry.get("effect_id")
    if target_side is None or effect_id is None:
        return
    active = self._get_active_for_side(target_side)
    if active is None:
        return
    buffs = active.setdefault("buffs", [])
    stage = entry.get("effect_stage")
    ename = entry.get("effect_name")
    # BuffChangeType: 0=NULL, 1=ADD, 2=CHANGE, 3=REMOVE
    if stage == 3:
        # 移除 buff
        active["buffs"] = [b for b in buffs if b.get("id") != effect_id]
        return
    existing = next((b for b in buffs if b["id"] == effect_id), None)
    if existing:
        if stage is not None:
            existing["stage"] = stage
            existing.update(enrich_buff_modifiers(existing))
        existing["turns_applied"] = existing.get("turns_applied", 0) + 1
    else:
        buffs.append(enrich_buff_modifiers({
            "id": effect_id,
            "name": ename or str(effect_id),
            "stage": stage,
            "source_skill": (entry.get("related_skills") or [{}])[0].get("skill_name") if entry.get("related_skills") else None,
            "turns_applied": 1,
        }))
    self._attach_reflect_confirmed_effect(active, entry, source="protocol_effect_apply")
    if effect_id in POISON_BUFF_IDS:
        active["poison_stacks"] = stage if stage is not None else active.get("poison_stacks", 0) + 1

def _handle_effect_stage_entry(self, entry: Dict[str, Any]) -> None:
    actor_side = entry.get("actor_side")
    effect_id = entry.get("effect_id")
    new_stage = entry.get("effect_stage")
    if actor_side is None:
        return
    active = self._get_active_for_side(actor_side)
    if active is not None:
        buffs = active.get("buffs", [])
        existing = next((b for b in buffs if b["id"] == effect_id), None)
        if existing and new_stage is not None:
            existing["stage"] = new_stage
            existing.update(enrich_buff_modifiers(existing))

def _append_pet_effect_history(self, entry: Dict[str, Any], event_kind: str) -> None:
    side = entry.get("target_side") or entry.get("actor_side")
    active = self._get_active_for_side(side) if side is not None else None
    target = active if active is not None else self.state
    target.setdefault("effect_history", []).append({
        "kind": event_kind,
        "effect_id": entry.get("effect_id"),
        "effect_name": entry.get("effect_name"),
        "effect_base": entry.get("effect_base"),
        "actor_side": entry.get("actor_side"),
        "target_side": entry.get("target_side"),
        "round": self.state["round"],
        "event_ordinal": entry.get("event_ordinal"),
    })

def _handle_effect_link_entry(self, entry: Dict[str, Any]) -> None:
    self._append_pet_effect_history(entry, "effect_link")

def _handle_effect_trigger_entry(self, entry: Dict[str, Any]) -> None:
    self._append_pet_effect_history(entry, "effect_trigger")

def _handle_buff_trigger_entry(self, entry: Dict[str, Any]) -> None:
    self._append_pet_effect_history(entry, "buff_trigger")
    side = entry.get("target_side") or entry.get("actor_side")
    active = self._get_active_for_side(side) if side is not None else None
    if active is None:
        return
    if self._is_generic_reflect_trigger(entry):
        self._record_reflect_candidates(active, entry)
        return
    self._attach_reflect_confirmed_effect(active, entry, source="protocol_buff_trigger")

def _is_generic_reflect_trigger(entry: Dict[str, Any]) -> bool:
    ids = {entry.get("effect_id"), entry.get("buff_id")}
    bases = set(entry.get("buffbase_ids") or [])
    if entry.get("effect_base") is not None:
        bases.add(entry.get("effect_base"))
    effect_name = str(entry.get("effect_name") or "")
    return (
        REFLECT_BUFF_ID in ids
        or REFLECT_BUFFBASE_ID in bases
        or "折射" in effect_name
    )

def _record_reflect_candidates(self, active: Dict[str, Any], entry: Dict[str, Any]) -> None:
    candidates = build_reflect_candidate_effects(active)
    record = {
        "round": self.state.get("round", 0),
        "opcode": self._current_opcode,
        "packet_index": (self._current_event_detail or {}).get("packet_index"),
        "event_ordinal": entry.get("event_ordinal"),
        "actor_side": entry.get("actor_side"),
        "target_side": entry.get("target_side"),
        "pet_id": active.get("pet_id"),
        "pet_name": active.get("name"),
        "candidate_effects": copy.deepcopy(candidates),
        "source": "reflect_trigger_skill_pool",
    }
    record = {k: v for k, v in record.items() if v not in (None, [], {})}
    active["reflect_candidate_effects"] = copy.deepcopy(candidates)
    self._append_bounded(
        self._field_context().setdefault("reflect_candidates", []),
        record,
        MAX_REFLECT_CANDIDATES,
    )

def _attach_reflect_confirmed_effect(
    self,
    active: Dict[str, Any],
    entry: Dict[str, Any],
    *,
    source: str,
) -> None:
    effect = (
        reflect_effect_for_buff(entry.get("effect_id"), entry.get("effect_name"))
        or reflect_effect_for_buff(entry.get("buff_id"), entry.get("effect_name"))
    )
    if not effect:
        return
    buffs = active.setdefault("buffs", [])
    reflect = next((b for b in buffs if b.get("id") == REFLECT_BUFF_ID), None)
    if reflect is None:
        reflect = {
            "id": REFLECT_BUFF_ID,
            "name": "折射",
            "stage": 1,
            "turns_applied": 0,
        }
        buffs.append(reflect)

    derived = reflect.setdefault("derived_buffs", [])
    child_id = effect["effect_buff_id"]
    if not any((item.get("id") if isinstance(item, dict) else item) == child_id for item in derived):
        derived.append({
            "id": child_id,
            "name": effect["effect_name"],
            "source": source,
            "parent_buff_id": REFLECT_BUFF_ID,
            "parent_buffbase_id": REFLECT_BUFFBASE_ID,
            "wrapper_buff_id": effect.get("wrapper_buff_id"),
            "element_id": effect.get("element_id"),
            "element_name": effect.get("element_name"),
            "kind": effect.get("kind"),
            "round": self.state.get("round"),
            "event_ordinal": entry.get("event_ordinal"),
        })
    effects = reflect.setdefault("derived_effects", [])
    if not any(item.get("id") == child_id and item.get("source") == source for item in effects):
        effects.append({
            "id": child_id,
            "kind": effect.get("kind"),
            "name": effect["effect_name"],
            "element_id": effect.get("element_id"),
            "element_name": effect.get("element_name"),
            "source": source,
            "round": self.state.get("round"),
            "event_ordinal": entry.get("event_ordinal"),
        })
    reflect.update(enrich_buff_modifiers(reflect))
    active["reflect_confirmed_effects"] = copy.deepcopy(reflect.get("derived_effects", []))

    # 变身/模型切换场景中，活跃 battler 和原宠记录会同时保留同一侧的折射 buff。
    # 将已确认的派生效果同步回同侧记录，避免预测读取阵容宠物时丢掉 modifier。
    active_side = active.get("side")
    if active_side is None:
        return
    for pet in self.state.get("my_pets", []) + self.state.get("opp_pets", []):
        if pet is active or pet.get("side") != active_side:
            continue
        other = next((b for b in pet.get("buffs", []) if b.get("id") == REFLECT_BUFF_ID), None)
        if other is None:
            continue
        other["derived_buffs"] = copy.deepcopy(reflect.get("derived_buffs", []))
        other["derived_effects"] = copy.deepcopy(reflect.get("derived_effects", []))
        other.update(enrich_buff_modifiers(other))
        pet["reflect_confirmed_effects"] = copy.deepcopy(reflect.get("derived_effects", []))
