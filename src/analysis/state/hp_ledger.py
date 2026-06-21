"""HP update and damage-ledger helpers for battle state tracking."""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional

MAX_DAMAGE_LEDGER = 600
MAX_PET_HP_TRACE = 160


def as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def next_ledger_id(tracker: Any) -> str:
    ledger = tracker._field_context().setdefault("damage_ledger", [])
    detail = tracker._current_event_detail or {}
    packet = detail.get("packet_index", "p?")
    return f"r{tracker.state.get('round', 0)}:{packet}:{len(ledger) + 1}"


def apply_hp_update(
    tracker: Any,
    pet: Optional[Dict[str, Any]],
    *,
    event_kind: str,
    entry: Optional[Dict[str, Any]] = None,
    side: Any = None,
    target_pet_id: Any = None,
    hp_change: Any = None,
    hp_result: Any = None,
    target_hp_after: Any = None,
    actual_damage: Any = None,
    source_hint: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Apply a server-authoritative HP update and append ledger/trace records."""
    entry = entry or {}
    hp_before = as_int(pet.get("current_hp")) if pet is not None else None
    max_hp = as_int(pet.get("max_hp")) if pet is not None else None
    hp_delta = as_int(hp_change)
    result_hp = as_int(hp_result)
    entry_hp_after = as_int(target_hp_after)
    damage_value = as_int(actual_damage)
    raw_after: Optional[int] = None
    source = source_hint or "unknown"

    if result_hp is not None:
        raw_after = result_hp
        source = "hp_result"
    elif entry_hp_after is not None:
        raw_after = entry_hp_after
        source = "target_hp_after"
    else:
        source = "missing_server_hp"

    anomalies: list[str] = []
    if pet is None:
        anomalies.append("target_unresolved")
    if raw_after is None:
        anomalies.append("missing_hp_after")

    hp_after = raw_after
    if hp_after is not None:
        if hp_after < 0:
            anomalies.append("negative_hp")
            hp_after = 0
        if max_hp is not None and max_hp > 0 and hp_after > max_hp:
            anomalies.append("hp_exceeds_max")
            hp_after = max_hp
        if hp_before is not None and hp_delta is not None and hp_after - hp_before != hp_delta:
            anomalies.append("hp_change_mismatch")
        if (
            event_kind == "damage"
            and hp_before is not None
            and damage_value is not None
            and max(0, hp_before - hp_after) != damage_value
        ):
            anomalies.append("damage_hp_mismatch")

    confidence = "high"
    if source == "missing_server_hp":
        confidence = "low"
    if anomalies:
        confidence = "low" if "target_unresolved" in anomalies or "missing_hp_after" in anomalies else "medium"

    if pet is not None and hp_after is not None:
        pet["current_hp"] = hp_after
        if max_hp is not None and max_hp > 0:
            pet["hp_pct"] = hp_after / max_hp
        else:
            pet["hp_pct"] = 1.0 if hp_after > 0 else 0.0

    detail = tracker._current_event_detail or {}
    ledger = {
        "ledger_id": next_ledger_id(tracker),
        "round": tracker.state.get("round", 0),
        "opcode": tracker._current_opcode if tracker._current_opcode is not None else detail.get("opcode"),
        "packet_index": detail.get("packet_index", entry.get("packet_index")),
        "event_ordinal": entry.get("event_ordinal"),
        "event_kind": event_kind,
        "group_id": entry.get("group_id"),
        "exec_index": entry.get("exec_index"),
        "skill_id": entry.get("skill_id"),
        "skill_name": entry.get("skill_name"),
        "target_pet_id": target_pet_id if target_pet_id is not None else (pet or {}).get("pet_id"),
        "side": side if side is not None else entry.get("target_side") or entry.get("damage_target_side"),
        "hp_before": hp_before,
        "hp_change": hp_delta,
        "hp_result": result_hp,
        "target_hp_after": entry_hp_after,
        "hp_after": hp_after,
        "raw_hp_after": raw_after,
        "max_hp": max_hp,
        "source": source,
        "confidence": confidence,
        "original_damage": entry.get("original_damage"),
        "damage_change": entry.get("damage_change"),
        "damage_result": entry.get("damage_result"),
        "actual_damage": damage_value,
        "damage": entry.get("damage"),
        "is_critical": entry.get("is_critical"),
        "restraint_type": entry.get("restraint_type"),
        "anomalies": anomalies,
    }
    ledger = {k: v for k, v in ledger.items() if v not in (None, [], {})}
    tracker._append_bounded(
        tracker._field_context().setdefault("damage_ledger", []),
        ledger,
        MAX_DAMAGE_LEDGER,
    )
    if pet is not None:
        tracker._append_bounded(
            pet.setdefault("hp_trace", []),
            copy.deepcopy(ledger),
            MAX_PET_HP_TRACE,
        )
        if event_kind == "damage":
            pet["last_damage_event"] = copy.deepcopy(ledger)
            if ledger.get("damage_result") is not None:
                pet["last_damage_result"] = ledger["damage_result"]
            if ledger.get("original_damage") is not None:
                pet["last_original_damage"] = ledger["original_damage"]
        else:
            pet["last_hp_event"] = copy.deepcopy(ledger)
    if entry is not None:
        entry["ledger_id"] = ledger["ledger_id"]
        if ledger.get("target_pet_id") is not None:
            entry["target_pet_id"] = ledger["target_pet_id"]
        if hp_before is not None:
            entry["hp_before"] = hp_before
        if hp_after is not None:
            entry["hp_after"] = hp_after
    return ledger
