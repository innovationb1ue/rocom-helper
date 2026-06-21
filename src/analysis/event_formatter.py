"""战斗事件格式化模块 — 将原始协议事件转换为结构化显示数据。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.analysis.constants import (
    OPCODE_ACTION_ACK,
    OPCODE_ACTION_RESOLVE,
    OPCODE_BATTLE_ENTER,
    OPCODE_BATTLE_FINISH,
    OPCODE_PREPLAY,
    OPCODE_PVP_PERFORM,
    OPCODE_ROUND_FLOW,
    OPCODE_ROUND_START,
    OPCODE_SKILL_DECLARE,
    OPCODE_SKILL_SELECT,
    OPCODE_SPECIAL_REFRESH,
)
from src.analysis.formatting.core import (
    FormattedEvent,
    side_label,
)
from src.analysis.formatting.entry_dispatch import format_action_entry
from src.analysis.formatting.lifecycle import (
    format_action_ack,
    format_battle_enter,
    format_battle_finish,
    format_round_flow,
    format_round_start,
    format_skill_declare,
    format_skill_select,
    format_special_refresh,
)
from src.analysis.formatting.merge import merge_damage_events as _merge_damage_events


# ---------------------------------------------------------------------------
# Top-level dispatch
# ---------------------------------------------------------------------------

def format_battle_event(
    opcode: int,
    detail: Dict[str, Any],
    state: Dict[str, Any],
    round_num: int = 0,
) -> List[FormattedEvent]:
    """Format a single protocol event into one or more FormattedEvents."""
    events: List[FormattedEvent] = []

    if opcode == OPCODE_BATTLE_ENTER:
        ev = format_battle_enter(detail, state)
        ev.round = round_num
        events.append(ev)

    elif opcode == OPCODE_ROUND_START:
        ev = format_round_start(detail, state)
        events.append(ev)

    elif opcode == OPCODE_BATTLE_FINISH:
        ev = format_battle_finish(detail, state)
        events.append(ev)

    elif opcode == OPCODE_SKILL_SELECT:
        ev = format_skill_select(detail)
        ev.round = round_num
        events.append(ev)

    elif opcode == OPCODE_SKILL_DECLARE:
        ev = format_skill_declare(detail)
        ev.round = round_num
        events.append(ev)

    elif opcode == OPCODE_ACTION_ACK:
        ev = format_action_ack(detail)
        ev.round = round_num
        events.append(ev)

    elif opcode == OPCODE_SPECIAL_REFRESH:
        ev = format_special_refresh(detail)
        ev.round = round_num
        events.append(ev)

    elif opcode == OPCODE_ROUND_FLOW:
        ev = format_round_flow(detail)
        events.append(ev)

    elif opcode in (OPCODE_ACTION_RESOLVE, OPCODE_PVP_PERFORM, OPCODE_PREPLAY):
        for entry in detail.get("entries", []):
            ev = format_action_entry(entry, state, round_num)
            if ev is not None:
                events.append(ev)
        events = _merge_damage_events(events)

    return events
