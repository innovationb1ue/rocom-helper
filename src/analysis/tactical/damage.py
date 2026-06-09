"""战术排序使用的伤害和属性对位工具。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.analysis.damage_prediction import DamagePredictionService
from src.game.type_chart import TypeChart


class TacticalDamageToolkit:
    """封装 TacticalEngine 需要的伤害预测口径。"""

    def __init__(
        self,
        chart: Optional[TypeChart] = None,
        *,
        prediction_service: Optional[DamagePredictionService] = None,
    ) -> None:
        self.chart = chart or TypeChart()
        self._prediction_service = prediction_service or DamagePredictionService(self.chart)

    @property
    def prediction_service(self) -> DamagePredictionService:
        return self._prediction_service

    def calc_damage(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        skill_meta: Optional[Dict[str, Any]],
        weather: Optional[Dict[str, Any]],
    ) -> int:
        """返回与技能分析面板一致的战术总伤害。"""
        if skill_meta is None:
            return 0
        damage_type = skill_meta.get("damage_type", 0)
        if damage_type not in (2, 3):
            return 0
        predicted = self._prediction_service.predict(attacker, defender, skill_meta, weather=weather)
        if predicted is None:
            return 0
        prediction = predicted.get("prediction") or {}
        return int(prediction.get("tactical_total") or prediction.get("total") or 0)

    def type_matchup_score(
        self,
        our_pet: Dict[str, Any],
        opp_pet: Dict[str, Any],
    ) -> float:
        """计算我方对敌方的最佳属性克制倍率。"""
        our_types = our_pet.get("types", [])
        opp_types = opp_pet.get("types", [])
        if not our_types or not opp_types:
            return 1.0

        best = 0.0
        for attack_type in our_types:
            multiplier = self.chart.get_multiplier(attack_type, opp_types)
            if multiplier > best:
                best = multiplier
        return best
