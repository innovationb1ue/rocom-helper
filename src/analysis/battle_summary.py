"""Battle summary builders."""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.constants import OPCODE_LABELS


def compute_battle_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    my_pets_final = []
    for p in state.get("my_pets", []):
        my_pets_final.append({
            "name": p.get("name", "?"),
            "hp": p.get("current_hp", 0),
            "max_hp": p.get("max_hp", 0),
            "status": "战败" if p.get("current_hp", 0) <= 0 else "存活",
        })
    opp_pets_final = []
    for p in state.get("opp_pets", []):
        opp_pets_final.append({
            "name": p.get("name", "?"),
            "hp": p.get("current_hp", 0),
            "max_hp": p.get("max_hp", 0),
            "status": "战败" if p.get("current_hp", 0) <= 0 else "存活",
        })

    event_stats: Dict[str, int] = {}
    for event in state.get("events", []):
        opcode = event.get("opcode", 0)
        key = OPCODE_LABELS.get(opcode, hex(opcode))
        event_stats[key] = event_stats.get(key, 0) + 1

    return {
        "result": state.get("result"),
        "rounds": state.get("round"),
        "my_pets_final": my_pets_final,
        "opp_pets_final": opp_pets_final,
        "event_stats": event_stats,
    }
