"""Shared battle replay/WebSocket message builders."""
from __future__ import annotations

from typing import Any, Dict, List, cast

from src.analysis.contracts import BattleWebSocketMessage
from src.analysis.battle_summary import compute_battle_summary
from src.analysis.constants import OPCODE_BATTLE_FINISH
from src.analysis.models import ProcessResult


def build_battle_frame(
    opcode: int,
    result: ProcessResult,
    *,
    stream_id: str,
    seq: int,
    event_index: int,
) -> Dict[str, Any]:
    """Build the authoritative ordered WebSocket frame for one processed event."""
    context = _analysis_context(result.state)
    battle_summary = (
        compute_battle_summary(result.state)
        if opcode == OPCODE_BATTLE_FINISH
        else None
    )
    battle_advice = result.battle_advice or {}
    frame: Dict[str, Any] = {
        "type": "battle_frame",
        "stream_id": stream_id,
        "seq": seq,
        "event_index": event_index,
        "opcode": opcode,
        "round": int(result.state.get("round") or 0),
        "state": result.state,
        "events": [event.to_dict() for event in result.formatted_events],
        "suggestions": result.suggestions,
        "skills": battle_advice.get("skill_analysis", []),
        "traits": battle_advice.get("traits", []),
        "opp_traits": battle_advice.get("opp_traits", []),
        "opp_skill_analysis": battle_advice.get("opp_skill_analysis", []),
        "opp_skill_source": battle_advice.get("opp_skill_source", ""),
        "hook_advice": result.hook_advice,
        "tactical_recommendations": result.tactical,
        "battle_summary": battle_summary,
        "has_battle_advice": result.battle_advice is not None,
        "has_hook_advice": bool(result.hook_advice),
        "has_tactical_recommendations": result.tactical is not None,
        **context,
    }
    return frame


def build_battle_messages(
    opcode: int,
    result: ProcessResult,
) -> List[BattleWebSocketMessage]:
    """Build browser-visible messages from a processed battle event."""
    messages: List[BattleWebSocketMessage] = []
    context = _analysis_context(result.state)

    if result.formatted_events:
        if len(result.formatted_events) == 1:
            messages.append(
                {"type": "battle_event", "event": result.formatted_events[0].to_dict()}
            )
        else:
            messages.append(
                {
                    "type": "battle_events",
                    "events": [event.to_dict() for event in result.formatted_events],
                }
            )

    messages.append({"type": "state_update", "state": result.state})

    if result.suggestions:
        messages.append({"type": "suggestions", "suggestions": result.suggestions})

    if result.battle_advice:
        messages.append(
            {
                "type": "skill_analysis",
                "skills": result.battle_advice.get("skill_analysis", []),
                "traits": result.battle_advice.get("traits", []),
                "opp_traits": result.battle_advice.get("opp_traits", []),
                "opp_skill_analysis": result.battle_advice.get("opp_skill_analysis", []),
                "opp_skill_source": result.battle_advice.get("opp_skill_source", ""),
                **context,
            }
        )

    if result.hook_advice:
        messages.append({"type": "hook_advice", "advice": result.hook_advice})

    if result.tactical:
        messages.append(cast(BattleWebSocketMessage, {
            "type": "tactical_recommendations",
            **result.tactical,
            **context,
        }))

    if opcode == OPCODE_BATTLE_FINISH:
        messages.append(
            {"type": "battle_summary", "summary": compute_battle_summary(result.state)}
        )

    return messages


def _analysis_context(state: dict) -> dict:
    return {
        "round_number": int(state.get("round") or 0),
        "my_active_uid": _pet_identity(state.get("my_active") or {}),
        "opp_active_uid": _pet_identity(state.get("opp_active") or {}),
    }


def _pet_identity(pet: dict) -> str:
    if not pet:
        return ""
    for key in ("battle_uid", "pet_id", "base_id", "base_conf_id", "name"):
        value = pet.get(key)
        if value not in (None, ""):
            return f"{key}:{value}"
    return ""
