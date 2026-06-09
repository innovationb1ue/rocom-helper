"""战术推荐展示兼容门面。

单行动展示规则位于 action_presentation；整体推荐摘要和对手画像位于
recommendation_presentation。本模块保留旧函数名供兼容调用。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from src.analysis.models import ActionScore, OpponentAction
from src.analysis.tactical import action_presentation, recommendation_presentation


def action_category(
    our_action: Dict[str, Any],
    score: float,
    can_ko: bool,
    damage_taken: int,
    my_active: Dict[str, Any],
) -> str:
    return action_presentation.action_category(our_action, score, can_ko, damage_taken, my_active)


def expected_gain(
    our_action: Dict[str, Any],
    damage_dealt: int,
    can_ko: bool,
    metrics: Dict[str, Any],
) -> str:
    return action_presentation.expected_gain(our_action, damage_dealt, can_ko, metrics)


def risk_summary(
    our_action: Dict[str, Any],
    damage_taken: int,
    my_active: Dict[str, Any],
    unknowns: List[str],
) -> str:
    return action_presentation.risk_summary(our_action, damage_taken, my_active, unknowns)


def action_unknowns(
    our_action: Dict[str, Any],
    opp_active: Dict[str, Any],
    state: Dict[str, Any],
) -> List[str]:
    return action_presentation.action_unknowns(our_action, opp_active, state)


def action_confidence(
    unknowns: List[str],
    opp_active: Dict[str, Any],
    fallback: Callable[[Dict[str, Any]], str],
) -> str:
    return action_presentation.action_confidence(unknowns, opp_active, fallback)


def primary_plan(actions: List[ActionScore]) -> str:
    return recommendation_presentation.primary_plan(actions)


def build_warnings(
    actions: List[ActionScore],
    opp_predicted: List[OpponentAction],
    confidence: str,
    opp_skill_source: str,
) -> List[str]:
    return recommendation_presentation.build_warnings(actions, opp_predicted, confidence, opp_skill_source)


def opponent_profile(
    opp_active: Dict[str, Any],
    opp_predicted: List[OpponentAction],
    opp_skill_source: str,
) -> Dict[str, Any]:
    return recommendation_presentation.opponent_profile(opp_active, opp_predicted, opp_skill_source)


def opp_action_reason(skill_id: int, probability: float, opp_active: Dict[str, Any]) -> str:
    return recommendation_presentation.opp_action_reason(skill_id, probability, opp_active)
