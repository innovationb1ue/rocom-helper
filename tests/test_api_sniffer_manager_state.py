"""SnifferManager state container tests."""
from __future__ import annotations

from src.api.sniffer_manager_state import SnifferManagerState


def test_manager_state_defaults_match_legacy_initial_status():
    state = SnifferManagerState()

    assert state.state == "idle"
    assert state.message == "未启动"
    assert state.key_hex is None
    assert state.flow_count == 0


def test_set_state_returns_status_event_when_changed():
    state = SnifferManagerState()
    state.set_key_hex("313233")
    state.set_flow_count(2)

    event = state.set_state("connected", "游戏已连接")

    assert state.state == "connected"
    assert state.message == "游戏已连接"
    assert event == {
        "type": "status",
        "status": "connected",
        "message": "游戏已连接",
        "flow_count": 2,
        "key_hex": "313233",
    }


def test_set_state_returns_none_without_change():
    state = SnifferManagerState(state="listening", message="监听中")

    event = state.set_state("listening", "监听中")

    assert event is None


def test_flow_count_and_key_can_be_reset():
    state = SnifferManagerState(key_hex="abcd", flow_count=3)

    state.set_key_hex(None)
    state.set_flow_count(0)

    assert state.key_hex is None
    assert state.flow_count == 0
