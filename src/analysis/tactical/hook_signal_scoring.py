"""分析 hook 信号对战术行动评分的修饰。"""
from __future__ import annotations

from typing import Any, Dict, List


def apply_hook_signal_modifiers(
    score: float,
    our_action: Dict[str, Any],
    hook_signals: List[Dict[str, Any]],
) -> float:
    """根据 hook 输出的偏好/规避信号调整行动分数。"""
    for signal in hook_signals:
        if signal.get("signal_type") == "prefer_switch" and our_action["action_type"] == "switch":
            score *= 1.2
        elif signal.get("signal_type") == "avoid_skill" and our_action["action_type"] == "skill":
            energy_cost = our_action.get("energy_cost", 0)
            if energy_cost >= 3:
                score *= 0.5
            elif energy_cost >= 1:
                score *= 0.8
    return score
