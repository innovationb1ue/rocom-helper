"""TacticalEngine 的运行时和伤害工具兼容方法。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.models import OpponentAction
from src.analysis.tactical import recommendations, runtime as tactical_runtime, switch_targets


class TacticalRuntimeMixin:
    """保留 TacticalEngine 旧私有入口，实际逻辑委托给 runtime/damage/switch_targets。"""

    def _calc_damage(
        self, attacker: Dict[str, Any], defender: Dict[str, Any],
        skill_meta: Optional[Dict[str, Any]], weather: Optional[Dict[str, Any]],
    ) -> int:
        return self._damage.calc_damage(attacker, defender, skill_meta, weather)

    @staticmethod
    def _skill_runtime(pet: Dict[str, Any], skill_id: Any) -> Dict[str, Any]:
        return tactical_runtime.skill_runtime(pet, skill_id)

    @staticmethod
    def _skill_cd_round(skill: Dict[str, Any], runtime: Dict[str, Any]) -> int:
        return tactical_runtime.skill_cd_round(skill, runtime)

    @staticmethod
    def _resolve_action_energy_cost(
        skill: Dict[str, Any],
        runtime: Dict[str, Any],
        meta: Dict[str, Any],
    ) -> int:
        return tactical_runtime.resolve_action_energy_cost(skill, runtime, meta)

    @staticmethod
    def _skill_priority_layer(
        skill: Dict[str, Any],
        runtime: Dict[str, Any],
        meta: Dict[str, Any],
    ) -> int:
        return tactical_runtime.skill_priority_layer(skill, runtime, meta)

    def _type_matchup_score(
        self, our_pet: Dict[str, Any], opp_pet: Dict[str, Any],
    ) -> float:
        return self._damage.type_matchup_score(our_pet, opp_pet)

    @staticmethod
    def _normalize_pet_for_analysis(pet: Dict[str, Any]) -> Dict[str, Any]:
        return switch_targets.normalize_pet_for_analysis(pet)

    def _most_likely_switch_target(
        self,
        opp_action: OpponentAction, opp_pets: List[Dict[str, Any]],
        my_active: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        return self._switch_targets.most_likely_switch_target(opp_action, opp_pets, my_active)

    @staticmethod
    def _assess_confidence(opp_active: Dict[str, Any]) -> str:
        return recommendations.assess_confidence(opp_active)
