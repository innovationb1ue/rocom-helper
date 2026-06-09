"""Field/global event recording helpers for BattleStateTracker."""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional


MAX_SYNC_EVENTS = 300
MAX_PERFORM_GROUPS = 300

GLOBAL_EVENT_KINDS = {
    "weather_change",
    "notify_perform",
    "change_model",
    "data_update",
    "ai_action",
    "supply_pet",
    "buff_trigger",
    "effect_trigger",
    "effect_link",
    "cmd_failed",
    "runaway",
    "use_item",
}

COMMON_EVENT_FIELDS = [
    "type", "index", "phase_arg", "state_arg", "extra_arg",
    "group_id", "cast_moment", "is_group_head", "group_ref",
    "is_last_hit", "exec_index",
]

PAYLOAD_FIELDS_BY_KIND = {
    "weather_change": COMMON_EVENT_FIELDS + [
        "skill_id", "skill_name", "weather_id", "weather_name", "expire_round",
    ],
    "notify_perform": COMMON_EVENT_FIELDS + [
        "notify_type", "notify_data", "tips_id", "params", "uin",
    ],
    "change_model": COMMON_EVENT_FIELDS + [
        "pet_id", "old_base_id", "role_magic_flag", "model_pet_id",
        "model_base_id", "model_pet_name", "model_battle_stats",
        "model_current_hp", "model_max_hp", "original_pet_id",
        "original_pet_name", "original_pet_types", "original_pet_level",
        "original_base_conf_id",
    ],
    "data_update": COMMON_EVENT_FIELDS + ["uin", "pet_id", "pet_skill_updates"],
    "ai_action": COMMON_EVENT_FIELDS + ["pet_id", "uin", "ai_type", "param"],
    "supply_pet": COMMON_EVENT_FIELDS + ["player_id", "supply_pets"],
    "effect_trigger": COMMON_EVENT_FIELDS + [
        "actor_side", "actor_side_name", "target_side", "target_side_name",
        "effect_id", "effect_name",
    ],
    "effect_link": COMMON_EVENT_FIELDS + [
        "actor_side", "actor_side_name", "target_side", "target_side_name",
        "effect_id", "effect_name",
    ],
    "buff_trigger": COMMON_EVENT_FIELDS + [
        "actor_side", "actor_side_name", "target_side", "target_side_name",
        "effect_id", "effect_name", "buff_id", "buffbase_ids",
        "perform_type", "need_select_pet", "frozen_death",
    ],
    "cmd_failed": COMMON_EVENT_FIELDS + ["failed_reason"],
    "runaway": COMMON_EVENT_FIELDS + [
        "actor_side", "actor_side_name", "target_side", "target_side_name",
    ],
    "use_item": COMMON_EVENT_FIELDS + ["caster_id", "target_id", "item_id"],
}


def global_event_base(tracker: Any, kind: str, entry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    entry = entry or {}
    detail = tracker._current_event_detail or {}
    out = {
        "round": tracker.state.get("round", 0),
        "opcode": tracker._current_opcode if tracker._current_opcode is not None else detail.get("opcode"),
        "packet_index": detail.get("packet_index", entry.get("packet_index")),
        "event_ordinal": entry.get("event_ordinal"),
        "kind": kind,
        "parse_quality": detail.get("parse_quality") or entry.get("parse_quality"),
        "source": detail.get("schema_message") or detail.get("semantic_level") or entry.get("source"),
    }
    return {k: v for k, v in out.items() if v is not None}


def global_event_payload(tracker: Any, kind: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    payload = tracker._pick(entry, PAYLOAD_FIELDS_BY_KIND.get(kind, COMMON_EVENT_FIELDS))
    if kind == "weather_change":
        payload["weather_name"] = tracker._weather_name(
            payload.get("weather_id"), payload.get("weather_name")
        )
    return payload


def record_global_event(
    tracker: Any,
    kind: str,
    entry: Dict[str, Any],
    *,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    record = global_event_base(tracker, kind, entry)
    record.update(payload if payload is not None else global_event_payload(tracker, kind, entry))
    tracker._field_context().setdefault("global_events", []).append(record)
    return record


def record_perform_group(tracker: Any, entry: Dict[str, Any]) -> None:
    payload = tracker._pick(entry, [
        "type", "kind", "group_id", "cast_moment", "is_group_head",
        "group_ref", "is_last_hit", "exec_index", "event_ordinal",
    ])
    if not payload:
        return
    payload.update({
        "round": tracker.state.get("round", 0),
        "packet_index": (tracker._current_event_detail or {}).get("packet_index"),
    })
    payload = {k: v for k, v in payload.items() if v is not None}
    tracker._append_bounded(
        tracker._field_context().setdefault("perform_groups", []),
        payload,
        MAX_PERFORM_GROUPS,
    )


def record_sync_event(tracker: Any, entry: Dict[str, Any]) -> None:
    sync_data = entry.get("sync_data") or {}
    if not sync_data:
        return
    payload = tracker._pick(entry, ["kind", "type", "group_id", "exec_index", "event_ordinal"])
    payload.update({
        "round": tracker.state.get("round", 0),
        "packet_index": (tracker._current_event_detail or {}).get("packet_index"),
        "sync_data": copy.deepcopy(sync_data),
    })
    tracker._append_bounded(
        tracker._field_context().setdefault("sync_events", []),
        payload,
        MAX_SYNC_EVENTS,
    )


def record_item_sync_events(tracker: Any, entry: Dict[str, Any]) -> None:
    for item in (entry.get("sync_data") or {}).get("item_sync", []) or []:
        payload = {
            "round": tracker.state.get("round", 0),
            "packet_index": (tracker._current_event_detail or {}).get("packet_index"),
            "group_id": entry.get("group_id"),
            **copy.deepcopy(item),
        }
        tracker._append_bounded(
            tracker._field_context().setdefault("item_sync_events", []),
            {k: v for k, v in payload.items() if v is not None},
            MAX_SYNC_EVENTS,
        )
