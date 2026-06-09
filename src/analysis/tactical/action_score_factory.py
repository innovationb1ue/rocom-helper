"""ActionScore 构造和候选行动排序。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from src.analysis.models import ActionScore

ScoreActionFn = Callable[[Dict[str, Any]], Tuple[float, str, Dict[str, Any]]]


def action_score_from_detail(
    our_action: Dict[str, Any],
    score: float,
    reason: str,
    detail: Dict[str, Any],
) -> ActionScore:
    return ActionScore(
        action_type=our_action["action_type"],
        skill_id=our_action.get("skill_id"),
        skill_name=our_action.get("skill_name"),
        switch_to_name=our_action.get("switch_to_name"),
        score=round(score, 4),
        reason=reason,
        category=detail.get("category", "balanced"),
        expected_gain=detail.get("expected_gain", ""),
        risk=detail.get("risk", ""),
        confidence=detail.get("confidence", "medium"),
        damage_dealt=detail.get("damage_dealt"),
        damage_taken=detail.get("damage_taken"),
        can_ko=detail.get("can_ko", False),
        energy_cost=our_action.get("energy_cost", 0),
        metrics=detail.get("metrics", {}),
        unknowns=detail.get("unknowns", []),
    )


def score_action_candidates(
    our_actions: List[Dict[str, Any]],
    *,
    score_action: ScoreActionFn,
) -> List[ActionScore]:
    """把候选行动评分并按高到低排序。"""
    scored = [
        action_score_from_detail(our_action, *score_action(our_action))
        for our_action in our_actions
    ]
    scored.sort(key=lambda action: action.score, reverse=True)
    return scored
