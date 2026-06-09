"""BattleProcessor 的格式化输出与 ProcessResult 组装 helpers。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from src.analysis.event_formatter import format_battle_event
from src.analysis.formatting.core import FormattedEvent
from src.analysis.models import ProcessResult
from src.analysis.suggestions import build_state_suggestions

FormatEventFn = Callable[[int, Dict[str, Any], Dict[str, Any], int], List[FormattedEvent]]
SuggestionsFn = Callable[[Dict[str, Any]], List[Dict[str, str]]]


def build_formatted_events(
    *,
    include_formatting: bool,
    opcode: int,
    detail: Dict[str, Any],
    state: Dict[str, Any],
    round_num: int,
    formatter: FormatEventFn = format_battle_event,
) -> List[FormattedEvent]:
    if not include_formatting:
        return []
    return formatter(opcode, detail, state, round_num)


def build_suggestions(
    state: Dict[str, Any],
    *,
    suggestions_fn: SuggestionsFn = build_state_suggestions,
) -> List[Dict[str, str]]:
    return suggestions_fn(state)


def build_process_result(
    *,
    state: Dict[str, Any],
    formatted_events: List[FormattedEvent],
    battle_advice: Optional[Dict[str, Any]],
    hook_advice: List[Dict[str, Any]],
    suggestions: List[Dict[str, str]],
    tactical: Optional[Dict[str, Any]],
) -> ProcessResult:
    return ProcessResult(
        state=state,
        formatted_events=formatted_events,
        battle_advice=battle_advice,
        hook_advice=hook_advice,
        suggestions=suggestions,
        tactical=tactical,
    )
