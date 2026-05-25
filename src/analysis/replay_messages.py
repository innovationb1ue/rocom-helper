"""Shared battle replay/WebSocket message builders."""
from __future__ import annotations

from typing import Any, Dict, List

from src.analysis.battle_processor import ProcessResult, compute_battle_summary


def build_battle_messages(
    opcode: int,
    result: ProcessResult,
) -> List[Dict[str, Any]]:
    """Build browser-visible messages from a processed battle event."""
    messages: List[Dict[str, Any]] = []

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
            }
        )

    if result.hook_advice:
        messages.append({"type": "hook_advice", "advice": result.hook_advice})

    if result.tactical:
        messages.append({"type": "tactical_recommendations", **result.tactical})

    if opcode == 0x132C:
        messages.append(
            {"type": "battle_summary", "summary": compute_battle_summary(result.state)}
        )

    return messages
