"""战术推荐结果组装兼容入口。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.analysis.models import ActionScore, OpponentAction, TacticalRecommendation
from src.analysis.tactical import action_score_factory
from src.analysis.tactical import recommendation_builder
from src.analysis.tactical import recommendation_confidence

ScoreActionFn = action_score_factory.ScoreActionFn
BattleMetricsFn = recommendation_builder.BattleMetricsFn


def assess_confidence(opp_active: Dict[str, Any]) -> str:
    """兼容入口：推荐置信度由 tactical.recommendation_confidence 负责。"""
    return recommendation_confidence.assess_confidence(opp_active)


def action_score_from_detail(
    our_action: Dict[str, Any],
    score: float,
    reason: str,
    detail: Dict[str, Any],
) -> ActionScore:
    return action_score_factory.action_score_from_detail(our_action, score, reason, detail)


def score_action_candidates(
    our_actions: List[Dict[str, Any]],
    *,
    score_action: ScoreActionFn,
) -> List[ActionScore]:
    """兼容入口：ActionScore 构造和排序由 tactical.action_score_factory 负责。"""
    return action_score_factory.score_action_candidates(our_actions, score_action=score_action)


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
    """兼容入口：TacticalRecommendation 构造由 tactical.recommendation_builder 负责。"""
    return recommendation_builder.build_recommendation(
        scored=scored,
        opp_predicted=opp_predicted,
        state=state,
        my_active=my_active,
        opp_active=opp_active,
        my_pets=my_pets,
        opp_pets=opp_pets,
        opp_skill_source=opp_skill_source,
        battle_metrics=battle_metrics,
    )
