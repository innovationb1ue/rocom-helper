"""TacticalEngine 的评分兼容方法。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.analysis.models import OpponentAction, ResolvedOutcome
from src.analysis.tactical import action_scoring, scoring


class TacticalScoringMixin:
    """保留 TacticalEngine 旧私有入口，实际逻辑委托给 action_scoring/scoring。"""

    def _score_action(
        self, our_action: Dict[str, Any], my_active: Dict[str, Any],
        opp_active: Dict[str, Any], my_pets: List[Dict[str, Any]],
        opp_pets: List[Dict[str, Any]], opp_predicted: List[OpponentAction],
        state: Dict[str, Any], top_threat_name: Optional[str] = None,
    ) -> Tuple[float, str, Dict[str, Any]]:
        return action_scoring.score_action(
            our_action,
            my_active,
            opp_active,
            my_pets,
            opp_pets,
            opp_predicted,
            state,
            resolve_outcome=self._resolve_outcome,
            calc_damage=self._calc_damage,
            type_matchup_score=self._type_matchup_score,
            assess_confidence=self._assess_confidence,
            top_threat_name=top_threat_name,
        )

    def _evaluate_outcome(
        self, outcome: ResolvedOutcome,
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
    ) -> float:
        """将推演结果转为分数。"""
        return scoring.evaluate_outcome(outcome, my_active, opp_active)

    def _score_non_damage_skill(
        self, our_action: Dict[str, Any],
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
    ) -> Tuple[float, str, Dict[str, Any]]:
        return action_scoring.score_non_damage_skill(
            our_action,
            my_active,
            opp_active,
            assess_confidence=self._assess_confidence,
        )

    @staticmethod
    def _generate_reason(
        our_action: Dict[str, Any], damage_dealt: int, damage_taken: int, can_ko: bool,
    ) -> str:
        return action_scoring.generate_reason(our_action, damage_dealt, damage_taken, can_ko)

    def _action_metrics(
        self,
        *,
        our_action: Dict[str, Any],
        my_active: Dict[str, Any],
        opp_active: Dict[str, Any],
        damage_dealt: int,
        damage_taken: int,
        can_ko: bool,
    ) -> Dict[str, Any]:
        return action_scoring.action_metrics(
            our_action=our_action,
            my_active=my_active,
            opp_active=opp_active,
            damage_dealt=damage_dealt,
            damage_taken=damage_taken,
            can_ko=can_ko,
            type_matchup_score=self._type_matchup_score,
        )

    def _battle_metrics(
        self,
        my_active: Dict[str, Any],
        opp_active: Dict[str, Any],
        my_pets: List[Dict[str, Any]],
        opp_pets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return action_scoring.battle_metrics(
            my_active,
            opp_active,
            my_pets,
            opp_pets,
            type_matchup_score=self._type_matchup_score,
        )
