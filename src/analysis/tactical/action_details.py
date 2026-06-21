"""战术行动 detail 兼容门面。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from src.analysis.tactical import action_metrics as action_metrics_module
from src.analysis.tactical import action_reason

TypeMatchupFn = Callable[[Dict[str, Any], Dict[str, Any]], float]


def generate_reason(
    our_action: Dict[str, Any],
    damage_dealt: int,
    damage_taken: int,
    can_ko: bool,
) -> str:
    """兼容入口：推荐理由由 tactical.action_reason 负责。"""
    return action_reason.generate_reason(our_action, damage_dealt, damage_taken, can_ko)


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
    """兼容入口：单行动 cockpit 指标由 tactical.action_metrics 负责。"""
    return action_metrics_module.action_metrics(
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
    """兼容入口：整场 cockpit 指标由 tactical.action_metrics 负责。"""
    return action_metrics_module.battle_metrics(
        my_active,
        opp_active,
        my_pets,
        opp_pets,
        type_matchup_score=type_matchup_score,
    )
