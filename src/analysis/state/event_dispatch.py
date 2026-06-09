"""Top-level battle state event logging and opcode dispatch."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator

from src.analysis.constants import (
    OPCODE_ACTION_ACK,
    OPCODE_ACTION_RESOLVE,
    OPCODE_BATTLE_ENTER,
    OPCODE_BATTLE_FINISH,
    OPCODE_ROUND_FLOW,
    OPCODE_ROUND_START,
    OPCODE_SKILL_DECLARE,
    OPCODE_SKILL_SELECT,
    OPCODE_SPECIAL_REFRESH,
)


DISPATCHERS = {
    OPCODE_BATTLE_ENTER: "_handle_battle_enter",
    OPCODE_ROUND_START: "_handle_round_start",
    OPCODE_ACTION_RESOLVE: "_handle_action_resolve",
    OPCODE_ACTION_ACK: "_handle_action_ack",
    OPCODE_BATTLE_FINISH: "_handle_battle_finish",
    OPCODE_SKILL_SELECT: "_handle_skill_select",
    OPCODE_SPECIAL_REFRESH: "_handle_special_refresh",
    OPCODE_SKILL_DECLARE: "_handle_skill_declare",
    OPCODE_ROUND_FLOW: "_handle_round_flow",
}


def append_protocol_event(state: Dict[str, Any], opcode: int, detail: Dict[str, Any]) -> Dict[str, Any]:
    """Append the raw protocol event to state history using the current round."""
    event = {"opcode": opcode, "round": state["round"]}
    event.update(detail)
    state["events"].append(event)
    return event


@contextmanager
def current_event_context(tracker: Any, opcode: int, detail: Dict[str, Any]) -> Iterator[None]:
    """Expose the current event to entry handlers, then always clear it."""
    tracker._current_opcode = opcode
    tracker._current_event_detail = detail
    tracker._ctx.current_opcode = opcode
    tracker._ctx.current_event_detail = detail
    try:
        yield
    finally:
        tracker._current_opcode = None
        tracker._current_event_detail = {}
        tracker._ctx.current_opcode = None
        tracker._ctx.current_event_detail = {}


def dispatch_protocol_event(tracker: Any, opcode: int, detail: Dict[str, Any]) -> None:
    """Dispatch a logged protocol event to the matching tracker handler."""
    handler_name = DISPATCHERS.get(opcode)
    if handler_name is None:
        return
    getattr(tracker, handler_name)(detail)


def apply_protocol_event(tracker: Any, opcode: int, detail: Dict[str, Any]) -> None:
    """Record and dispatch one protocol event against a BattleStateTracker-like object."""
    append_protocol_event(tracker.state, opcode, detail)
    with current_event_context(tracker, opcode, detail):
        dispatch_protocol_event(tracker, opcode, detail)
