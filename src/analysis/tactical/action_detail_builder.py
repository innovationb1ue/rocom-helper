"""战术行动前端 detail 字段构造。"""
from __future__ import annotations

from typing import Any, Callable, Dict

from src.analysis.tactical import action_details, action_outcome_scoring, presentation

TypeMatchupFn = Callable[[Dict[str, Any], Dict[str, Any]], float]
AssessConfidenceFn = Callable[[Dict[str, Any]], str]


def build_action_detail(
    our_action: Dict[str, Any],
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    state: Dict[str, Any],
    outcome_score: action_outcome_scoring.ActionOutcomeScore,
    total_score: float,
    *,
    type_matchup_score: TypeMatchupFn,
    assess_confidence: AssessConfidenceFn,
) -> Dict[str, Any]:
    """构造前端 ActionScore 需要的 detail dict。"""
    metrics = action_details.action_metrics(
        our_action=our_action,
        my_active=my_active,
        opp_active=opp_active,
        damage_dealt=outcome_score.shown_damage,
        damage_taken=outcome_score.worst_damage_taken,
        can_ko=outcome_score.shown_can_ko,
        type_matchup_score=type_matchup_score,
    )
    unknowns = presentation.action_unknowns(our_action, opp_active, state)
    return {
        "damage_dealt": display_damage(outcome_score),
        "damage_taken": (
            outcome_score.worst_damage_taken
            if outcome_score.worst_damage_taken > 0
            else None
        ),
        "can_ko": outcome_score.shown_can_ko,
        "category": presentation.action_category(
            our_action,
            total_score,
            outcome_score.shown_can_ko,
            outcome_score.worst_damage_taken,
            my_active,
        ),
        "expected_gain": presentation.expected_gain(
            our_action,
            outcome_score.shown_damage,
            outcome_score.shown_can_ko,
            metrics,
        ),
        "risk": presentation.risk_summary(
            our_action,
            outcome_score.worst_damage_taken,
            my_active,
            unknowns,
        ),
        "confidence": presentation.action_confidence(unknowns, opp_active, assess_confidence),
        "metrics": metrics,
        "unknowns": unknowns,
    }


def display_damage(outcome_score: action_outcome_scoring.ActionOutcomeScore) -> int | None:
    if outcome_score.display_damage_dealt and outcome_score.display_damage_dealt > 0:
        return outcome_score.display_damage_dealt
    return None
