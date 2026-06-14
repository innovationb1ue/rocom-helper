"""TacticalRecommendation 结果组装。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from src.analysis.models import ActionScore, OpponentAction, TacticalRecommendation
from src.analysis.tactical import presentation, recommendation_confidence

BattleMetricsFn = Callable[
    [Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]],
    Dict[str, Any],
]


def build_recommendation(
    *,
    scored: List[ActionScore],
    opp_predicted: List[OpponentAction],
    state: Dict[str, Any],
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    my_pets: List[Dict[str, Any]],
    opp_pets: List[Dict[str, Any]],
    opp_skill_source: str,
    battle_metrics: BattleMetricsFn,
) -> TacticalRecommendation:
    model_confidence = recommendation_confidence.assess_confidence(opp_active)
    confidence = _action_confidence(scored, model_confidence)
    warnings = presentation.build_warnings(scored, opp_predicted, model_confidence, opp_skill_source)

    return TacticalRecommendation(
        actions=scored,
        opp_predicted=opp_predicted,
        round_number=state.get("round", 0),
        confidence=confidence,
        model_confidence=model_confidence,
        primary_plan=presentation.primary_plan(scored),
        warnings=warnings,
        metrics=battle_metrics(my_active, opp_active, my_pets, opp_pets),
        opponent_profile=presentation.opponent_profile(opp_active, opp_predicted, opp_skill_source),
    )


def _action_confidence(scored: List[ActionScore], fallback: str) -> str:
    if not scored:
        return fallback
    return scored[0].confidence or fallback
