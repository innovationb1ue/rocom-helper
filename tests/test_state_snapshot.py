"""Battle state snapshot projection tests."""
from __future__ import annotations

from src.analysis.state import snapshot


def test_build_state_snapshot_deep_copies_and_adds_effective_speed():
    state = {
        "my_pets": [{"name": "A", "base_speed": 100, "buffs": []}],
        "opp_pets": [{"name": "B", "base_speed": None, "buffs": []}],
        "my_active": {"name": "A", "base_speed": 100, "buffs": []},
        "opp_active": {"name": "B", "base_speed": None, "buffs": []},
    }

    result = snapshot.build_state_snapshot(state)

    assert result is not state
    assert result["my_pets"][0] is not state["my_pets"][0]
    assert result["my_pets"][0]["effective_speed"] == 100
    assert result["my_active"]["effective_speed"] == 100
    assert result["opp_pets"][0]["effective_speed"] is None
    assert "effective_speed" not in state["my_pets"][0]


def test_build_state_snapshot_preserves_active_pet_identity_within_snapshot():
    active = {"name": "A", "base_speed": 100, "buffs": []}
    state = {
        "my_pets": [active],
        "opp_pets": [],
        "my_active": active,
        "opp_active": None,
    }

    result = snapshot.build_state_snapshot(state)

    assert result["my_active"] is result["my_pets"][0]
    assert result["my_active"] is not active


def test_clone_state_value_isolates_nested_lists_and_dicts():
    state = {
        "events": [{"entries": [{"kind": "damage"}]}],
    }

    result = snapshot.clone_state_value(state)
    result["events"][0]["entries"][0]["kind"] = "changed"

    assert state["events"][0]["entries"][0]["kind"] == "damage"


def test_clone_event_history_copies_list_and_event_dicts_but_not_payloads():
    payload = [{"kind": "damage"}]
    events = [{"opcode": 1, "entries": payload}]

    result = snapshot.clone_event_history(events)
    result.append({"opcode": 2})
    result[0]["opcode"] = 9

    assert events == [{"opcode": 1, "entries": payload}]
    assert result[0]["entries"] is payload


def test_build_state_snapshot_uses_event_history_fast_path():
    payload = [{"kind": "damage"}]
    state = {
        "events": [{"opcode": 1, "entries": payload}],
        "my_pets": [],
        "opp_pets": [],
        "my_active": None,
        "opp_active": None,
    }

    result = snapshot.build_state_snapshot(state)

    assert result["events"] is not state["events"]
    assert result["events"][0] is not state["events"][0]
    assert result["events"][0]["entries"] is payload


def test_compute_effective_speed_combines_flat_percent_and_stat_modifiers(monkeypatch):
    from src.data import loader

    monkeypatch.setattr(loader, "get_speed_buff_modifiers", lambda buffs: {"flat_total": 10, "pct_total": 0.2})
    monkeypatch.setattr(loader, "get_buff_stat_modifiers", lambda buffs: {"spd_up": 0.1, "spd_down": 0.05})

    assert snapshot.compute_effective_speed({"base_speed": 100, "buffs": [{"id": 1}]}) == 138


def test_compute_effective_speed_returns_none_without_base_speed():
    assert snapshot.compute_effective_speed({"buffs": []}) is None
