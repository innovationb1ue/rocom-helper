"""Rule-based state suggestions."""
from __future__ import annotations

from typing import Any, Dict, List


def build_state_suggestions(state: Dict[str, Any]) -> List[Dict[str, str]]:
    suggestions: List[Dict[str, str]] = []
    seen: set = set()
    my_active = state.get("my_active")
    opp_active = state.get("opp_active")

    if my_active is None or opp_active is None:
        return suggestions

    if my_active.get("hp_pct", 1.0) < 0.25:
        suggestions.append({"type": "low_hp", "message": "我方精灵HP过低，考虑换宠"})

    if opp_active.get("hp_pct", 1.0) < 0.25:
        suggestions.append({"type": "finish_off", "message": "对手精灵HP极低，可尝试击杀"})

    if my_active.get("energy", 0) < 2:
        suggestions.append({"type": "low_energy", "message": "能量不足，考虑使用低能耗技能或能量瓶"})

    negative_buffs = [b for b in my_active.get("buffs", []) if b.get("stacks", 0) < 0]
    if len(negative_buffs) >= 2:
        suggestions.append({"type": "debuffed", "message": "我方精灵有多个负面状态"})

    unique: List[Dict[str, str]] = []
    for suggestion in suggestions:
        key = (suggestion["type"], suggestion["message"])
        if key not in seen:
            seen.add(key)
            unique.append(suggestion)
    return unique
