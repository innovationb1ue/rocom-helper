"""战术行动对预测对手行动的 outcome 聚合评分。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.analysis.models import OpponentAction, ResolvedOutcome
from src.analysis.tactical import scoring

ResolveOutcomeFn = Callable[
    [Dict[str, Any], OpponentAction, Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]],
    ResolvedOutcome,
]
CalcDamageFn = Callable[[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]], int]


@dataclass(frozen=True)
class ActionOutcomeScore:
    total_score: float
    best_damage_dealt: int
    worst_damage_taken: int
    can_ko: bool
    display_damage_dealt: Optional[int]
    display_can_ko: bool

    @property
    def shown_damage(self) -> int:
        return self.display_damage_dealt or self.best_damage_dealt

    @property
    def shown_can_ko(self) -> bool:
        return self.display_can_ko or self.can_ko


def score_expected_outcomes(
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
    top_threat_name: Optional[str] = None,
) -> ActionOutcomeScore:
    """计算行动在所有对手预测行动上的期望 outcome 摘要。"""
    display_damage_dealt = preview_damage(our_action, my_active, opp_active, state, calc_damage)
    display_can_ko = bool(
        display_damage_dealt
        and display_damage_dealt > 0
        and display_damage_dealt >= opp_active.get("current_hp", 0)
    )

    total_score = 0.0
    best_damage_dealt = 0
    worst_damage_taken = 0
    can_ko = False

    for opp_act in opp_predicted:
        outcome = resolve_outcome(
            our_action,
            opp_act,
            my_active,
            opp_active,
            my_pets,
            opp_pets,
            state,
        )
        outcome_score = scoring.evaluate_outcome(outcome, my_active, opp_active)
        total_score += opp_act.probability * outcome_score

        best_damage_dealt = max(best_damage_dealt, outcome.our_damage_dealt)
        worst_damage_taken = max(worst_damage_taken, outcome.opp_damage_dealt)
        can_ko = can_ko or outcome.we_ko

    if top_threat_name and opp_active.get("name") == top_threat_name and can_ko:
        total_score *= 1.15

    return ActionOutcomeScore(
        total_score=total_score,
        best_damage_dealt=best_damage_dealt,
        worst_damage_taken=worst_damage_taken,
        can_ko=can_ko,
        display_damage_dealt=display_damage_dealt,
        display_can_ko=display_can_ko,
    )


def preview_damage(
    our_action: Dict[str, Any],
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    state: Dict[str, Any],
    calc_damage: CalcDamageFn,
) -> Optional[int]:
    """为展示字段预先计算伤害技能的直接伤害。"""
    if our_action["action_type"] != "skill" or not our_action.get("is_damage_skill", False):
        return None
    return calc_damage(
        my_active,
        opp_active,
        our_action.get("meta"),
        state.get("weather"),
    )
