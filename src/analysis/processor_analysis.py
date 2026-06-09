"""BattleProcessor 的伤害分析与战术推荐 helpers。"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from src.analysis.constants import OPCODE_ACTION_RESOLVE
from src.analysis.prediction_reliability import build_prediction_reliability
from src.analysis.state_projector import project_state_after_entries


class BattleAdviceLike(Protocol):
    skill_analysis: list

    def to_dict(self) -> Dict[str, Any]: ...


class AdvisorLike(Protocol):
    def analyze(self, state: Dict[str, Any]) -> BattleAdviceLike: ...


class TacticalRecommendationLike(Protocol):
    actions: list

    def to_dict(self) -> Dict[str, Any]: ...


class TacticalEngineLike(Protocol):
    def recommend(self, state: Dict[str, Any]) -> Optional[TacticalRecommendationLike]: ...


def compute_damage_analysis(
    state: Dict[str, Any],
    *,
    advisor: AdvisorLike,
) -> Optional[Dict[str, Any]]:
    advice = advisor.analyze(state)
    if not advice.skill_analysis:
        return None
    return advice.to_dict()


def has_usable_damage_predictions(advice: Optional[Dict[str, Any]]) -> bool:
    if not advice:
        return False
    for skill in advice.get("skill_analysis", []):
        if skill.get("skill_damage_type") not in (2, 3):
            continue
        if skill.get("expected_damage") is not None:
            return True
    return False


def compute_damage_analysis_for_event(
    *,
    opcode: int,
    detail: Dict[str, Any],
    state: Dict[str, Any],
    state_before: Optional[Dict[str, Any]],
    advisor: AdvisorLike,
) -> Optional[Dict[str, Any]]:
    if opcode != OPCODE_ACTION_RESOLVE:
        return compute_damage_analysis(state, advisor=advisor)

    projected = project_state_after_entries(state_before or state, detail.get("entries", []))
    advice = compute_damage_analysis(projected, advisor=advisor)
    if has_usable_damage_predictions(advice):
        return advice
    return compute_damage_analysis(state, advisor=advisor)


def compute_tactical(
    state: Dict[str, Any],
    *,
    engine: TacticalEngineLike,
) -> Optional[Dict[str, Any]]:
    recommendation = engine.recommend(state)
    if recommendation is None or not recommendation.actions:
        return None
    return recommendation.to_dict()


def compute_tactical_with_reliability(
    state: Dict[str, Any],
    *,
    engine: TacticalEngineLike,
    battle_advice: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    tactical = compute_tactical(state, engine=engine)
    if tactical is None:
        return None
    tactical["reliability"] = build_prediction_reliability(
        state=state,
        battle_advice=battle_advice,
        tactical=tactical,
    )
    return tactical
