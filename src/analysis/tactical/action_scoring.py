"""单个我方行动的期望评分聚合。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from src.analysis.models import OpponentAction, ResolvedOutcome
from src.analysis.tactical import action_details
from src.analysis.tactical import action_detail_builder
from src.analysis.tactical import action_outcome_scoring
from src.analysis.tactical import hook_signal_scoring
from src.analysis.tactical import non_damage_scoring

ResolveOutcomeFn = Callable[
    [Dict[str, Any], OpponentAction, Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]],
    ResolvedOutcome,
]
CalcDamageFn = Callable[[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]], int]
TypeMatchupFn = Callable[[Dict[str, Any], Dict[str, Any]], float]
AssessConfidenceFn = Callable[[Dict[str, Any]], str]


def score_action(
    our_action: Dict[str, Any],
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    my_pets: List[Dict[str, Any]],
    opp_pets: List[Dict[str, Any]],
    opp_predicted: List[OpponentAction],
    state: Dict[str, Any],
    *,
    resolve_outcome: ResolveOutcomeFn,
    calc_damage: CalcDamageFn,
    type_matchup_score: TypeMatchupFn,
    assess_confidence: AssessConfidenceFn,
    top_threat_name: Optional[str] = None,
) -> Tuple[float, str, Dict[str, Any]]:
    """对单个操作计算期望得分和前端 detail。"""
    if our_action["action_type"] == "skill" and not our_action.get("is_damage_skill", False):
        return score_non_damage_skill(
            our_action,
            my_active,
            opp_active,
            assess_confidence=assess_confidence,
        )

    outcome_score = action_outcome_scoring.score_expected_outcomes(
        our_action,
        my_active,
        opp_active,
        my_pets,
        opp_pets,
        opp_predicted,
        state,
        resolve_outcome=resolve_outcome,
        calc_damage=calc_damage,
        top_threat_name=top_threat_name,
    )
    total_score = apply_hook_signal_modifiers(outcome_score.total_score, our_action, state.get("_hook_signals", []))

    reason = generate_reason(
        our_action,
        outcome_score.shown_damage,
        outcome_score.worst_damage_taken,
        outcome_score.shown_can_ko,
    )
    detail = action_detail_builder.build_action_detail(
        our_action,
        my_active,
        opp_active,
        state,
        outcome_score,
        total_score,
        type_matchup_score=type_matchup_score,
        assess_confidence=assess_confidence,
    )
    return total_score, reason, detail


def apply_hook_signal_modifiers(
    score: float,
    our_action: Dict[str, Any],
    hook_signals: List[Dict[str, Any]],
) -> float:
    """兼容入口：hook 信号加权由 tactical.hook_signal_scoring 负责。"""
    return hook_signal_scoring.apply_hook_signal_modifiers(score, our_action, hook_signals)


def score_non_damage_skill(
    our_action: Dict[str, Any],
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    *,
    assess_confidence: AssessConfidenceFn,
) -> Tuple[float, str, Dict[str, Any]]:
    """兼容入口：非伤害技能评分由 tactical.non_damage_scoring 负责。"""
    return non_damage_scoring.score_non_damage_skill(
        our_action,
        my_active,
        opp_active,
        assess_confidence=assess_confidence,
    )


def generate_reason(
    our_action: Dict[str, Any],
    damage_dealt: int,
    damage_taken: int,
    can_ko: bool,
) -> str:
    """生成中文推荐理由。"""
    return action_details.generate_reason(our_action, damage_dealt, damage_taken, can_ko)


def action_metrics(
    *,
    our_action: Dict[str, Any],
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    damage_dealt: int,
    damage_taken: int,
    can_ko: bool,
    type_matchup_score: TypeMatchupFn,
) -> Dict[str, Any]:
    return action_details.action_metrics(
        our_action=our_action,
        my_active=my_active,
        opp_active=opp_active,
        damage_dealt=damage_dealt,
        damage_taken=damage_taken,
        can_ko=can_ko,
        type_matchup_score=type_matchup_score,
    )


def battle_metrics(
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    my_pets: List[Dict[str, Any]],
    opp_pets: List[Dict[str, Any]],
    *,
    type_matchup_score: TypeMatchupFn,
) -> Dict[str, Any]:
    return action_details.battle_metrics(
        my_active,
        opp_active,
        my_pets,
        opp_pets,
        type_matchup_score=type_matchup_score,
    )
