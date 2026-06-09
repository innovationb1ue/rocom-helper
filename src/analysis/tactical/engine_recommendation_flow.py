"""TacticalEngine.recommend 的编排 flow。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from src.analysis.models import ActionScore, OpponentAction, TacticalRecommendation
from src.analysis.tactical import recommendations, threats
from src.game.type_chart import TypeChart

EnumerateActionsFn = Callable[[Dict[str, Any], List[Dict[str, Any]]], List[Dict[str, Any]]]
OppSkillSourceFn = Callable[[Dict[str, Any]], str]
PredictOpponentFn = Callable[[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]], List[OpponentAction]]
ScoreActionFn = Callable[
    [
        Dict[str, Any],
        Dict[str, Any],
        Dict[str, Any],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        List[OpponentAction],
        Dict[str, Any],
        str | None,
    ],
    Tuple[float, str, Dict[str, Any]],
]
BattleMetricsFn = recommendations.BattleMetricsFn


def recommend_from_state(
    state: Dict[str, Any],
    *,
    chart: TypeChart,
    enumerate_actions: EnumerateActionsFn,
    opp_skill_source: OppSkillSourceFn,
    predict_opponent: PredictOpponentFn,
    score_action: ScoreActionFn,
    battle_metrics: BattleMetricsFn,
) -> Optional[TacticalRecommendation]:
    """根据状态和注入依赖执行 tactical recommendation flow。"""
    my_active = state.get("my_active")
    opp_active = state.get("opp_active")
    my_pets = state.get("my_pets", [])
    opp_pets = state.get("opp_pets", [])
    if not my_active or not opp_active:
        return None

    our_actions = enumerate_actions(my_active, my_pets)
    if not our_actions:
        return None

    source = opp_skill_source(opp_active)
    opp_predicted = predict_opponent(opp_active, opp_pets, state)
    if not opp_predicted:
        return None

    top_threat_name = threats.top_threat_name(opp_pets, my_active, chart=chart)
    scored = recommendations.score_action_candidates(
        our_actions,
        score_action=lambda our_action: score_action(
            our_action,
            my_active,
            opp_active,
            my_pets,
            opp_pets,
            opp_predicted,
            state,
            top_threat_name,
        ),
    )

    return recommendations.build_recommendation(
        scored=scored,
        opp_predicted=opp_predicted,
        state=state,
        my_active=my_active,
        opp_active=opp_active,
        my_pets=my_pets,
        opp_pets=opp_pets,
        opp_skill_source=source,
        battle_metrics=battle_metrics,
    )
