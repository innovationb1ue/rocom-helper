"""Battle state top-level event dispatch tests."""
from __future__ import annotations

import pytest

from src.analysis.constants import OPCODE_BATTLE_ENTER
from src.analysis.state import event_dispatch


class FakeContext:
    def __init__(self) -> None:
        self.current_opcode = None
        self.current_event_detail = {}


class FakeTracker:
    def __init__(self) -> None:
        self.state = {"round": 7, "events": []}
        self._current_opcode = None
        self._current_event_detail = {}
        self._ctx = FakeContext()
        self.calls = []

    def _handle_battle_enter(self, detail):
        self.calls.append((
            "_handle_battle_enter",
            detail,
            self._current_opcode,
            self._current_event_detail,
            self._ctx.current_opcode,
            self._ctx.current_event_detail,
        ))


def test_apply_protocol_event_logs_event_and_dispatches_with_current_context():
    tracker = FakeTracker()
    detail = {"battle_id": "b1"}

    event_dispatch.apply_protocol_event(tracker, OPCODE_BATTLE_ENTER, detail)

    assert tracker.state["events"] == [{"opcode": OPCODE_BATTLE_ENTER, "round": 7, "battle_id": "b1"}]
    assert tracker.calls == [
        (
            "_handle_battle_enter",
            detail,
            OPCODE_BATTLE_ENTER,
            detail,
            OPCODE_BATTLE_ENTER,
            detail,
        )
    ]
    assert tracker._current_opcode is None
    assert tracker._current_event_detail == {}
    assert tracker._ctx.current_opcode is None
    assert tracker._ctx.current_event_detail == {}


def test_apply_protocol_event_keeps_unknown_opcode_as_history_only():
    tracker = FakeTracker()

    event_dispatch.apply_protocol_event(tracker, 0xFFFF, {"kind": "unknown"})

    assert tracker.state["events"] == [{"opcode": 0xFFFF, "round": 7, "kind": "unknown"}]
    assert tracker.calls == []


def test_current_event_context_clears_context_after_handler_error(monkeypatch):
    tracker = FakeTracker()

    def boom(_detail):
        raise RuntimeError("boom")

    monkeypatch.setattr(tracker, "_handle_battle_enter", boom)

    with pytest.raises(RuntimeError, match="boom"):
        event_dispatch.apply_protocol_event(tracker, OPCODE_BATTLE_ENTER, {})

    assert tracker._current_opcode is None
    assert tracker._current_event_detail == {}
    assert tracker._ctx.current_opcode is None
    assert tracker._ctx.current_event_detail == {}
