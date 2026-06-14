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
    if state.get("result"):
        return None
    opp_pets = state.get("opp_pets") or []
    if opp_pets and not any((pet.get("current_hp") or 0) > 0 for pet in opp_pets):
        return None
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
    apply_prediction_guardrails(tactical, battle_advice)
    sync_tactical_confidence(tactical)
    return tactical


_SEVERE_QUALITY_FLAGS = {
    "runtime_target_unmatched",
    "uncalibrated_skill",
    "runtime_effect_unmodeled",
}


def apply_prediction_guardrails(
    tactical: Dict[str, Any],
    battle_advice: Optional[Dict[str, Any]],
) -> None:
    """Downgrade tactical actions whose damage prediction is explicitly unreliable."""
    if not tactical.get("actions"):
        return
    prediction_by_key = _prediction_quality_by_skill(battle_advice)
    changed = False
    for action in tactical.get("actions") or []:
        if action.get("action_type") != "skill":
            continue
        quality = prediction_by_key.get(_skill_key(action))
        if not quality:
            continue
        flags = set(quality.get("flags") or [])
        confidence = quality.get("confidence")
        severe = confidence == "low" or bool(flags & _SEVERE_QUALITY_FLAGS)
        if "multi_hit" in flags:
            action["score"] = round(float(action.get("score") or 0.0) - 0.08, 4)
            changed = True
        if not severe:
            continue
        action["score"] = round(float(action.get("score") or 0.0) - 0.18, 4)
        action["can_ko"] = False
        action["category"] = "confirm"
        action["confidence"] = "low"
        action["expected_gain"] = "预测低置信，先按待确认候选处理"
        action["reason"] = _downgraded_reason(action.get("damage_dealt"))
        unknowns = list(action.get("unknowns") or [])
        if "伤害预测低置信，击杀线需确认" not in unknowns:
            unknowns.append("伤害预测低置信，击杀线需确认")
        action["unknowns"] = unknowns
        metrics = dict(action.get("metrics") or {})
        metrics["can_ko"] = False
        action["metrics"] = metrics
        changed = True
    if changed:
        tactical["actions"] = sorted(
            tactical.get("actions") or [],
            key=lambda item: float(item.get("score") or 0.0),
            reverse=True,
        )
        tactical["primary_plan"] = _primary_plan(tactical["actions"])
        sync_tactical_confidence(tactical)


def sync_tactical_confidence(tactical: Dict[str, Any]) -> None:
    """Keep user-visible tactical confidence tied to the current top action."""
    actions = tactical.get("actions") or []
    if not actions:
        tactical["confidence"] = tactical.get("confidence") or tactical.get("model_confidence") or "medium"
        return
    tactical.setdefault("model_confidence", tactical.get("confidence") or "medium")
    tactical["confidence"] = actions[0].get("confidence") or tactical.get("model_confidence") or "medium"


def _prediction_quality_by_skill(
    battle_advice: Optional[Dict[str, Any]],
) -> Dict[tuple[Any, str], Dict[str, Any]]:
    result: Dict[tuple[Any, str], Dict[str, Any]] = {}
    if not battle_advice:
        return result
    for skill in battle_advice.get("skill_analysis") or []:
        prediction = skill.get("prediction") or {}
        flags = list(prediction.get("accuracy_flags") or [])
        quality = {
            "confidence": prediction.get("confidence") or skill.get("confidence"),
            "flags": flags,
        }
        result[_skill_key(skill)] = quality
    return result


def _skill_key(item: Dict[str, Any]) -> tuple[Any, str]:
    return (item.get("skill_id"), str(item.get("skill_name") or ""))


def _downgraded_reason(damage_dealt: Any) -> str:
    if damage_dealt:
        return f"预计约 {damage_dealt} 伤害，但预测低置信，不能按稳定击杀线处理"
    return "预测低置信，不能按稳定击杀线处理"


def _primary_plan(actions: list[Dict[str, Any]]) -> str:
    if not actions:
        return ""
    top = actions[0]
    name = f"换上 {top.get('switch_to_name')}" if top.get("action_type") == "switch" else (
        top.get("skill_name") or top.get("reason") or "行动"
    )
    if top.get("confidence") == "low":
        return f"待确认候选 {name}：{top.get('expected_gain') or top.get('reason') or ''}"
    return f"首选 {name}：{top.get('expected_gain') or top.get('reason') or ''}"
