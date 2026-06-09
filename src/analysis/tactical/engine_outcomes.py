"""TacticalEngine 的行动结果推演兼容方法。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.models import OpponentAction, ResolvedOutcome
from src.analysis.tactical import outcomes


class TacticalOutcomeMixin:
    """保留 TacticalEngine 旧私有入口，实际逻辑委托给 outcomes。"""

    def _resolve_outcome(
        self, our_action: Dict[str, Any], opp_action: OpponentAction,
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
        my_pets: List[Dict[str, Any]], opp_pets: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> ResolvedOutcome:
        return outcomes.resolve_outcome(
            our_action,
            opp_action,
            my_active,
            opp_active,
            my_pets,
            opp_pets,
            state,
            calc_damage=self._calc_damage,
            type_matchup_score=self._type_matchup_score,
            most_likely_switch_target=self._most_likely_switch_target,
        )

    def _resolve_skill_vs_skill(
        self, our_action: Dict[str, Any], opp_action: OpponentAction,
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
        state: Dict[str, Any], weather: Optional[Dict[str, Any]],
    ) -> ResolvedOutcome:
        return outcomes.resolve_skill_vs_skill(
            our_action,
            opp_action,
            my_active,
            opp_active,
            state,
            weather,
            calc_damage=self._calc_damage,
            type_matchup_score=self._type_matchup_score,
        )

    def _resolve_switch_outcome(
        self, our_action: Dict[str, Any], opp_action: OpponentAction,
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
        state: Dict[str, Any], weather: Optional[Dict[str, Any]],
    ) -> ResolvedOutcome:
        return outcomes.resolve_switch_outcome(
            our_action,
            opp_action,
            my_active,
            opp_active,
            state,
            weather,
            calc_damage=self._calc_damage,
            type_matchup_score=self._type_matchup_score,
        )

    def _resolve_opp_switch_outcome(
        self, our_action: Dict[str, Any], opp_action: OpponentAction,
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
        opp_pets: List[Dict[str, Any]], state: Dict[str, Any],
        weather: Optional[Dict[str, Any]],
    ) -> ResolvedOutcome:
        return outcomes.resolve_opp_switch_outcome(
            our_action,
            opp_action,
            my_active,
            opp_active,
            opp_pets,
            state,
            weather,
            calc_damage=self._calc_damage,
            type_matchup_score=self._type_matchup_score,
            most_likely_switch_target=self._most_likely_switch_target,
        )
