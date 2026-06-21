"""Field/global event recording helper tests."""
from __future__ import annotations

from src.analysis.battle_state import BattleStateTracker
from src.analysis.state import field_events


def _tracker() -> BattleStateTracker:
    tracker = BattleStateTracker()
    tracker.state["round"] = 6
    tracker._current_opcode = 0x1324
    tracker._current_event_detail = {
        "packet_index": 42,
        "parse_quality": "schema",
        "schema_message": "BattlePerformInfo",
    }
    return tracker


def test_record_global_event_builds_base_and_payload():
    tracker = _tracker()

    record = field_events.record_global_event(
        tracker,
        "notify_perform",
        {
            "event_ordinal": 9,
            "notify_type": 2,
            "tips_id": "weather_reject",
            "params": ["雨天"],
        },
    )

    assert record == {
        "round": 6,
        "opcode": 0x1324,
        "packet_index": 42,
        "event_ordinal": 9,
        "kind": "notify_perform",
        "parse_quality": "schema",
        "source": "BattlePerformInfo",
        "notify_type": 2,
        "tips_id": "weather_reject",
        "params": ["雨天"],
    }
    assert tracker.state["field_context"]["global_events"][-1] == record


def test_record_perform_group_filters_empty_and_bounds_history():
    tracker = _tracker()

    field_events.record_perform_group(tracker, {})
    assert tracker.state["field_context"]["perform_groups"] == []

    for idx in range(field_events.MAX_PERFORM_GROUPS + 2):
        field_events.record_perform_group(tracker, {
            "kind": "damage",
            "group_id": idx,
            "exec_index": idx,
        })

    groups = tracker.state["field_context"]["perform_groups"]
    assert len(groups) == field_events.MAX_PERFORM_GROUPS
    assert groups[0]["group_id"] == 2
    assert groups[-1]["packet_index"] == 42


def test_record_sync_event_deep_copies_and_records_item_sync():
    tracker = _tracker()
    entry = {
        "kind": "data_update",
        "group_id": 7,
        "sync_data": {
            "skill_sync": [{"pet_id": 1001, "skill_id": 7120090}],
            "item_sync": [{"item_id": 9001, "num": 2}],
        },
    }

    field_events.record_sync_event(tracker, entry)
    field_events.record_item_sync_events(tracker, entry)
    entry["sync_data"]["skill_sync"][0]["skill_id"] = 0
    entry["sync_data"]["item_sync"][0]["num"] = 0

    ctx = tracker.state["field_context"]
    assert ctx["sync_events"][-1]["sync_data"]["skill_sync"][0]["skill_id"] == 7120090
    assert ctx["sync_events"][-1]["packet_index"] == 42
    assert ctx["item_sync_events"][-1] == {
        "round": 6,
        "packet_index": 42,
        "group_id": 7,
        "item_id": 9001,
        "num": 2,
    }
