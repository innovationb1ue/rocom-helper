"""战术推荐引擎 — 基于期望值加权的行动排序系统。

对每个可选操作（4 技能 + 换宠）计算期望得分，考虑：
  - 对手行动的概率预测
  - 速度先后手与击杀否定
  - 伤害 / 存活 / 属性对位 / 能量效率
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.analysis.models import ActionScore, OpponentAction, ResolvedOutcome, TacticalRecommendation
from src.analysis.tactical import (
    damage as tactical_damage,
    engine_recommendation_flow,
    scoring,
    switch_targets,
)
from src.analysis.tactical.engine_actions import TacticalActionMixin
from src.analysis.tactical.engine_opponent import TacticalOpponentMixin
from src.analysis.tactical.engine_outcomes import TacticalOutcomeMixin
from src.analysis.tactical.engine_presentation import TacticalPresentationMixin
from src.analysis.tactical.engine_runtime import TacticalRuntimeMixin
from src.analysis.tactical.engine_scoring import TacticalScoringMixin
from src.game.type_chart import TypeChart

logger = logging.getLogger(__name__)

__all__ = [
    "ActionScore",
    "OpponentAction",
    "ResolvedOutcome",
    "TacticalEngine",
    "TacticalRecommendation",
    "W_COUNT_ADV",
    "W_DAMAGE_DEALT",
    "W_DAMAGE_TAKEN",
    "W_ENERGY",
    "W_KO",
    "W_OPP_KO",
    "W_TYPE_MATCHUP",
    "_clamp01",
]


# ---------------------------------------------------------------------------
# Evaluation weights
# ---------------------------------------------------------------------------

W_DAMAGE_DEALT = scoring.W_DAMAGE_DEALT
W_KO = scoring.W_KO
W_DAMAGE_TAKEN = scoring.W_DAMAGE_TAKEN
W_OPP_KO = scoring.W_OPP_KO
W_TYPE_MATCHUP = scoring.W_TYPE_MATCHUP
W_ENERGY = scoring.W_ENERGY
W_COUNT_ADV = scoring.W_COUNT_ADV


def _clamp01(x: float) -> float:
    return scoring.clamp01(x)


# ---------------------------------------------------------------------------
# TacticalEngine
# ---------------------------------------------------------------------------

class TacticalEngine(
    TacticalActionMixin,
    TacticalOpponentMixin,
    TacticalOutcomeMixin,
    TacticalScoringMixin,
    TacticalPresentationMixin,
    TacticalRuntimeMixin,
):
    """战术推荐引擎 — 为每个可选操作计算期望得分并排序。"""

    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self.chart = type_chart or TypeChart()
        self._damage = tactical_damage.TacticalDamageToolkit(self.chart)
        self._switch_targets = switch_targets.SwitchTargetResolver(self.chart)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend(self, state: Dict[str, Any]) -> Optional[TacticalRecommendation]:
        """根据当前战斗状态生成推荐行动排序。"""
        return engine_recommendation_flow.recommend_from_state(
            state,
            chart=self.chart,
            enumerate_actions=self._enumerate_our_actions,
            opp_skill_source=self._opp_skill_source,
            predict_opponent=self._predict_opp_actions,
            score_action=self._score_action,
            battle_metrics=self._battle_metrics,
        )
