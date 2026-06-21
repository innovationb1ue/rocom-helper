"""无头回放单事件处理与回合聚合 helper。"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from src.analysis.constants import OPCODE_ROUND_START
from src.analysis.models import ProcessResult
from src.analysis.replay_messages import build_battle_messages
from src.analysis.replay_models import ReplayEventSnapshot, RoundSnapshot
from src.protocol.opcodes import summarize
from src.protocol.proto_core import extract_inner_message

INNER_WRAPPER_OPCODE = 0x0414


def extract_replay_detail(record: Dict[str, Any], opcode: int) -> Tuple[str, Dict[str, Any]]:
    """Normalize a packet record into the detail consumed by BattleProcessor."""
    inner = None
    if opcode == INNER_WRAPPER_OPCODE:
        inner = extract_inner_message(record.get("root", {}))

    kind, summary = summarize(record, inner)
    detail = summary.get("detail", summary)
    if detail is None:
        detail = {}
    return kind, detail


def filter_process_result(
    result: ProcessResult,
    *,
    include_analysis: bool,
    include_hooks: bool,
    include_formatting: bool,
) -> Tuple[ProcessResult, List[Dict[str, Any]], Optional[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, str]]]:
    """Apply replay output flags without changing the processor state update."""
    formatted_dicts: List[Dict[str, Any]] = []
    if include_formatting:
        formatted_dicts = [copy.deepcopy(event.to_dict()) for event in result.formatted_events]

    battle_advice: Optional[Dict[str, Any]] = None
    if include_analysis:
        battle_advice = copy.deepcopy(result.battle_advice)

    hook_advice: List[Dict[str, Any]] = []
    if include_hooks:
        hook_advice = copy.deepcopy(result.hook_advice)

    suggestions = copy.deepcopy(result.suggestions)
    filtered = ProcessResult(
        state=result.state,
        formatted_events=result.formatted_events if include_formatting else [],
        battle_advice=battle_advice,
        hook_advice=hook_advice,
        suggestions=suggestions,
        tactical=copy.deepcopy(result.tactical) if include_analysis else None,
    )
    return filtered, formatted_dicts, battle_advice, hook_advice, suggestions


def build_replay_messages(opcode: int, result: ProcessResult) -> List[Dict[str, Any]]:
    """Build replay-visible messages through the shared WebSocket contract builder."""
    return list(build_battle_messages(opcode, result))


def make_event_snapshot(
    *,
    index: int,
    opcode: int,
    kind: str,
    round_num: int,
    state_before: Dict[str, Any],
    state_after: Dict[str, Any],
    formatted_events: List[Dict[str, Any]],
    battle_advice: Optional[Dict[str, Any]],
    hook_advice: List[Dict[str, Any]],
    suggestions: List[Dict[str, str]],
    tactical: Optional[Dict[str, Any]],
    messages: List[Dict[str, Any]],
) -> ReplayEventSnapshot:
    """Create the stable per-event snapshot stored in ReplayResult."""
    return ReplayEventSnapshot(
        index=index,
        opcode=opcode,
        kind=kind,
        round_num=round_num,
        state_before=state_before,
        state_after=state_after,
        formatted_events=formatted_events,
        battle_advice=battle_advice,
        hook_advice=hook_advice,
        suggestions=suggestions,
        tactical=tactical,
        messages=messages,
    )


def update_round_snapshot(
    round_map: Dict[int, RoundSnapshot],
    *,
    round_num: int,
    state_before: Dict[str, Any],
    state_after: Dict[str, Any],
    event: ReplayEventSnapshot,
    battle_advice: Optional[Dict[str, Any]],
    formatted_events: List[Dict[str, Any]],
    suggestions: List[Dict[str, str]],
    messages: List[Dict[str, Any]],
    tactical: Optional[Dict[str, Any]],
) -> RoundSnapshot:
    """Append one event into its round-level aggregate."""
    if round_num not in round_map:
        round_map[round_num] = RoundSnapshot(
            round_num=round_num,
            state_at_start=state_before,
        )
    round_snapshot = round_map[round_num]
    round_snapshot.events.append(event)
    round_snapshot.state_at_end = state_after
    round_snapshot.formatted_events.extend(formatted_events)
    round_snapshot.suggestions = list(suggestions)
    round_snapshot.messages.extend(messages)
    if battle_advice:
        round_snapshot.battle_advice = battle_advice
        round_snapshot.damage_predictions = battle_advice.get("skill_analysis", [])
        round_snapshot.traits = battle_advice.get("traits", [])
        round_snapshot.opp_traits = battle_advice.get("opp_traits", [])
        opp_skill_analysis = battle_advice.get("opp_skill_analysis", [])
        if opp_skill_analysis:
            round_snapshot.opp_skill_analysis = opp_skill_analysis
            round_snapshot.opp_skill_source = battle_advice.get("opp_skill_source", "")
    if tactical:
        round_snapshot.tactical_recommendations = tactical
    return round_snapshot


def should_stop_before_event(
    stop_round: Optional[int],
    current_state: Dict[str, Any],
    opcode: int,
    detail: Dict[str, Any],
) -> bool:
    """Return whether replay should stop before processing this event.

    `--round N` means replay all events that belong to round N and stop only
    before the first event of round N+1.  Finish packets are never inferred
    from defeat/resource counts and must be allowed through when they arrive.
    """
    if stop_round is None or opcode != OPCODE_ROUND_START:
        return False
    current_round = int(current_state.get("round") or 0)
    incoming_round = detail.get("round", current_round + 1)
    try:
        incoming_round = int(incoming_round)
    except (TypeError, ValueError):
        incoming_round = current_round + 1
    return incoming_round > stop_round


def should_stop_replay(stop_round: Optional[int], current_round: int, opcode: int) -> bool:
    """Compatibility helper for old callers; prefer should_stop_before_event."""
    return (
        stop_round is not None
        and opcode == OPCODE_ROUND_START
        and current_round > stop_round
    )
