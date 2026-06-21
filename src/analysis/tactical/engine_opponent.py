"""TacticalEngine 的对手行动预测兼容方法。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.analysis.models import OpponentAction
from src.analysis.tactical import opponent_model


class TacticalOpponentMixin:
    """保留 TacticalEngine 旧私有入口，实际逻辑委托给 opponent_model。"""

    def _predict_opp_actions(
        self, opp_active: Dict[str, Any], opp_pets: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> List[OpponentAction]:
        return opponent_model.predict_opponent_actions(
            opp_active,
            opp_pets,
            state,
            chart=self.chart,
            calc_damage=self._calc_damage,
        )

    @staticmethod
    def _resolve_opp_skills(opp_active: Dict[str, Any]) -> List[Dict[str, Any]]:
        return opponent_model.resolve_opp_skills(opp_active)

    def _compute_skill_probabilities(
        self, opp_skills: List[Dict[str, Any]], opp_energy: int,
        opp_active: Dict[str, Any],
    ) -> List[Tuple[int, float, str]]:
        return opponent_model.compute_skill_probabilities(opp_skills, opp_energy, opp_active)

    def _estimate_switch_probability(
        self, opp_active: Dict[str, Any], state: Dict[str, Any],
    ) -> float:
        return opponent_model.estimate_switch_probability(opp_active, state, chart=self.chart)

    @staticmethod
    def _opp_skill_source(opp_active: Dict[str, Any]) -> str:
        return opponent_model.opp_skill_source(opp_active)

    def _annotate_opp_threat(
        self,
        actions: List[OpponentAction],
        opp_active: Dict[str, Any],
        state: Dict[str, Any],
    ) -> None:
        opponent_model.annotate_opp_threat(
            actions,
            opp_active,
            state,
            calc_damage=self._calc_damage,
        )
