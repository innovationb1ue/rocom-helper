"""报告用轻量回放分析。

这里刻意不使用完整 ReplayResult，避免导出/接收报告时把每个事件的完整
state_before/state_after 都写入 JSON。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.battle_state import BattleStateTracker
from src.analysis.battle_summary import compute_battle_summary
from src.analysis.constants import OPCODE_BATTLE_FINISH
from src.analysis.event_formatter import format_battle_event
from src.analysis.suggestions import build_state_suggestions
from src.protocol.opcodes import summarize
from src.protocol.proto_core import extract_inner_message


def build_report_analysis(
    packets: List[Dict[str, Any]],
    *,
    include_events: bool = True,
) -> Dict[str, Any]:
    """Build a compact replay analysis without storing full per-event state copies."""
    tracker = BattleStateTracker()
    events: List[Dict[str, Any]] = []
    rounds: Dict[int, Dict[str, Any]] = {}
    messages: List[Dict[str, Any]] = []

    for index, item in enumerate(packets):
        record = item["record"]
        opcode = item["opcode"]
        inner = extract_inner_message(record.get("root", {})) if opcode == 0x0414 else None
        kind, summary = summarize(record, inner)
        detail = summary.get("detail", summary) if isinstance(summary, dict) else {}
        if not isinstance(detail, dict):
            detail = {}

        state = tracker.handle_event(opcode, detail)
        round_num = state.get("round", 0)
        formatted_events = [
            event.to_dict()
            for event in format_battle_event(opcode, detail, state, round_num)
        ]
        suggestions = build_state_suggestions(state)
        event_messages = compact_messages(opcode, state, formatted_events, suggestions)
        messages.extend(event_messages)

        round_bucket = rounds.setdefault(
            round_num,
            {
                "round_num": round_num,
                "formatted_events": [],
                "suggestions": [],
                "messages": [],
            },
        )
        round_bucket["formatted_events"].extend(formatted_events)
        round_bucket["suggestions"].extend(suggestions)
        round_bucket["messages"].extend(event_messages)

        if include_events:
            events.append(
                {
                    "index": index,
                    "opcode": opcode,
                    "kind": kind,
                    "round_num": round_num,
                    "filename": item.get("filename"),
                    "formatted_events": formatted_events,
                    "suggestions": suggestions,
                    "messages": event_messages,
                }
            )

    final_state = tracker.get_state()
    return {
        "total_packets": len(packets),
        "stopped_early": False,
        "rounds": [rounds[key] for key in sorted(rounds)],
        "events": events,
        "final_state": final_state,
        "battle_summary": compute_battle_summary(final_state),
        "messages": messages,
    }


def compact_messages(
    opcode: int,
    state: Dict[str, Any],
    formatted_events: List[Dict[str, Any]],
    suggestions: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    if len(formatted_events) == 1:
        messages.append({"type": "battle_event", "event": formatted_events[0]})
    elif len(formatted_events) > 1:
        messages.append({"type": "battle_events", "events": formatted_events})

    messages.append({
        "type": "state_update",
        "round": state.get("round", 0),
        "phase": state.get("phase"),
        "result": state.get("result"),
        "my_active": _pet_ref(state.get("my_active")),
        "opp_active": _pet_ref(state.get("opp_active")),
    })

    if suggestions:
        messages.append({"type": "suggestions", "suggestions": suggestions})
    if opcode == OPCODE_BATTLE_FINISH:
        messages.append({"type": "battle_summary", "summary": compute_battle_summary(state)})
    return messages


def _pet_ref(pet: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not pet:
        return None
    return {
        "pet_id": pet.get("pet_id"),
        "base_id": pet.get("base_id"),
        "battle_uid": pet.get("battle_uid"),
        "name": pet.get("name"),
        "current_hp": pet.get("current_hp"),
        "max_hp": pet.get("max_hp"),
        "energy": pet.get("energy"),
    }

