"""Battle state snapshot projection helpers."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

_IMMUTABLE_TYPES = (str, int, float, bool, type(None))


def build_state_snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-copy state and attach derived fields exposed to API/replay callers."""
    snapshot = clone_state_mapping(state)
    for key in ("my_pets", "opp_pets"):
        snapshot[key] = [
            pet for pet in snapshot.get(key, [])
            if not pet.get("supply_placeholder")
        ]
    for pet in snapshot.get("my_pets", []) + snapshot.get("opp_pets", []):
        pet["effective_speed"] = compute_effective_speed(pet)
    for key in ("my_active", "opp_active"):
        active = snapshot.get(key)
        if active:
            active["effective_speed"] = compute_effective_speed(active)
    return snapshot


def clone_state_mapping(state: Dict[str, Any]) -> Dict[str, Any]:
    """Clone top-level battle state with an event-history optimized path."""
    memo: Dict[int, Any] = {}
    snapshot: Dict[str, Any] = {}
    memo[id(state)] = snapshot
    for key, value in state.items():
        if key == "events" and isinstance(value, list):
            snapshot[key] = clone_event_history(value)
        else:
            snapshot[key] = clone_state_value(value, memo)
    return snapshot


def clone_event_history(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Clone append-only raw event history without recursively copying payloads.

    Event payloads are recorded once and not mutated by state handlers.  Copying
    the list and each event dict protects callers from changing the tracker
    history shape while avoiding expensive recursive cloning of old protocol
    payloads for every replay packet.
    """
    return [dict(event) for event in events]


def clone_state_value(value: Any, memo: Optional[Dict[int, Any]] = None) -> Any:
    """Clone battle-state JSON-like values faster than generic deepcopy.

    Battle state is intentionally dict/list/scalar shaped for API and replay
    serialization.  A small custom copier avoids the overhead of generic
    deepcopy while still preserving shared references within the snapshot, such
    as ``my_active`` pointing at the same copied pet object as ``my_pets[0]``.
    """
    if isinstance(value, _IMMUTABLE_TYPES):
        return value
    if memo is None:
        memo = {}
    value_id = id(value)
    if value_id in memo:
        return memo[value_id]
    if isinstance(value, dict):
        out: Dict[Any, Any] = {}
        memo[value_id] = out
        for key, item in value.items():
            out[clone_state_value(key, memo)] = clone_state_value(item, memo)
        return out
    if isinstance(value, list):
        out_list: List[Any] = []
        memo[value_id] = out_list
        out_list.extend(clone_state_value(item, memo) for item in value)
        return out_list
    if isinstance(value, tuple):
        out_tuple = tuple(clone_state_value(item, memo) for item in value)
        memo[value_id] = out_tuple
        return out_tuple
    return copy.deepcopy(value)


def compute_effective_speed(pet: Dict[str, Any]) -> Optional[int]:
    """计算实际速度 = (基础速度 + 固定修正) * (1 + 百分比修正 + 属性等级修正)。"""
    base = pet.get("base_speed")
    if base is None:
        return None
    from src.data.loader import get_buff_stat_modifiers, get_speed_buff_modifiers
    speed_mods = get_speed_buff_modifiers(pet.get("buffs", []))
    stat_mods = get_buff_stat_modifiers(pet.get("buffs", []))
    pct = (
        speed_mods.get("pct_total", 0.0)
        + stat_mods.get("spd_up", 0.0)
        - stat_mods.get("spd_down", 0.0)
    )
    effective = (base + speed_mods.get("flat_total", 0)) * (1.0 + pct)
    return max(1, int(round(effective)))
