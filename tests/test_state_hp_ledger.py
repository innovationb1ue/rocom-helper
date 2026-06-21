"""HP ledger helper tests."""
from __future__ import annotations

from src.analysis.battle_state import BattleStateTracker
from src.analysis.state.hp_ledger import apply_hp_update, as_int


def test_as_int_handles_missing_and_invalid_values():
    assert as_int(None) is None
    assert as_int("42") == 42
    assert as_int("bad") is None


def test_apply_hp_update_updates_pet_ledger_and_trace():
    tracker = BattleStateTracker()
    tracker.state["round"] = 3
    tracker._current_opcode = 0x1324
    tracker._current_event_detail = {"packet_index": 7}
    pet = {"pet_id": 101, "current_hp": 100, "max_hp": 120}
    entry = {
        "event_ordinal": 2,
        "skill_id": 1001,
        "skill_name": "测试技能",
        "actual_damage": 30,
    }

    ledger = apply_hp_update(
        tracker,
        pet,
        event_kind="damage",
        entry=entry,
        side=1,
        hp_result=70,
        actual_damage=30,
    )

    assert ledger["ledger_id"] == "r3:7:1"
    assert ledger["confidence"] == "high"
    assert ledger["hp_before"] == 100
    assert ledger["hp_after"] == 70
    assert pet["current_hp"] == 70
    assert pet["hp_pct"] == 70 / 120
    assert pet["last_damage_event"]["actual_damage"] == 30
    assert entry["ledger_id"] == ledger["ledger_id"]
    assert tracker.state["field_context"]["damage_ledger"][0] == ledger
    assert pet["hp_trace"][0]["ledger_id"] == ledger["ledger_id"]


def test_apply_hp_update_clamps_invalid_hp_and_marks_anomaly():
    tracker = BattleStateTracker()
    pet = {"pet_id": 101, "current_hp": 10, "max_hp": 50}

    ledger = apply_hp_update(
        tracker,
        pet,
        event_kind="heal",
        hp_result=80,
    )

    assert pet["current_hp"] == 50
    assert ledger["raw_hp_after"] == 80
    assert ledger["hp_after"] == 50
    assert ledger["confidence"] == "medium"
    assert "hp_exceeds_max" in ledger["anomalies"]


def test_apply_hp_update_records_unresolved_targets_without_mutating_pet():
    tracker = BattleStateTracker()

    ledger = apply_hp_update(
        tracker,
        None,
        event_kind="damage",
        side=401,
        actual_damage=12,
    )

    assert ledger["side"] == 401
    assert ledger["confidence"] == "low"
    assert ledger["anomalies"] == ["target_unresolved", "missing_hp_after"]
    assert tracker.state["field_context"]["damage_ledger"][0] == ledger
