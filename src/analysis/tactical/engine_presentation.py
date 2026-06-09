"""TacticalEngine 的战术展示文案兼容方法。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.analysis.models import ActionScore, OpponentAction
from src.analysis.tactical import presentation, recommendations


class TacticalPresentationMixin:
    """保留 TacticalEngine 旧私有入口，实际逻辑委托给 presentation。"""

    @staticmethod
    def _action_category(
        our_action: Dict[str, Any],
        score: float,
        can_ko: bool,
        damage_taken: int,
        my_active: Dict[str, Any],
    ) -> str:
        return presentation.action_category(our_action, score, can_ko, damage_taken, my_active)

    @staticmethod
    def _expected_gain(
        our_action: Dict[str, Any],
        damage_dealt: int,
        can_ko: bool,
        metrics: Dict[str, Any],
    ) -> str:
        return presentation.expected_gain(our_action, damage_dealt, can_ko, metrics)

    @staticmethod
    def _risk_summary(
        our_action: Dict[str, Any],
        damage_taken: int,
        my_active: Dict[str, Any],
        unknowns: List[str],
    ) -> str:
        return presentation.risk_summary(our_action, damage_taken, my_active, unknowns)

    @staticmethod
    def _action_unknowns(
        our_action: Dict[str, Any],
        opp_active: Dict[str, Any],
        state: Dict[str, Any],
    ) -> List[str]:
        return presentation.action_unknowns(our_action, opp_active, state)

    @staticmethod
    def _action_confidence(unknowns: List[str], opp_active: Dict[str, Any]) -> str:
        return presentation.action_confidence(unknowns, opp_active, recommendations.assess_confidence)

    @staticmethod
    def _primary_plan(actions: List[ActionScore]) -> str:
        return presentation.primary_plan(actions)

    @staticmethod
    def _build_warnings(
        actions: List[ActionScore],
        opp_predicted: List[OpponentAction],
        confidence: str,
        opp_skill_source: str,
    ) -> List[str]:
        return presentation.build_warnings(actions, opp_predicted, confidence, opp_skill_source)

    @staticmethod
    def _opponent_profile(
        opp_active: Dict[str, Any],
        opp_predicted: List[OpponentAction],
        opp_skill_source: str,
    ) -> Dict[str, Any]:
        return presentation.opponent_profile(opp_active, opp_predicted, opp_skill_source)

    @staticmethod
    def _opp_action_reason(skill_id: int, probability: float, opp_active: Dict[str, Any]) -> str:
        return presentation.opp_action_reason(skill_id, probability, opp_active)
