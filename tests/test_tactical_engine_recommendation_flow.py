"""TacticalEngine recommend 编排 flow 测试。"""
from __future__ import annotations

from src.analysis.models import OpponentAction
from src.analysis.tactical import engine_recommendation_flow
from src.game.type_chart import TypeChart


def _state():
    my = {"name": "我方", "current_hp": 100, "max_hp": 100, "types": [1], "energy": 5}
    opp = {"name": "敌方", "current_hp": 100, "max_hp": 100, "types": [1], "energy": 5}
    return {
        "round": 3,
        "my_active": my,
        "opp_active": opp,
        "my_pets": [my],
        "opp_pets": [opp],
    }


def test_recommend_from_state_returns_none_without_active_pets():
    assert engine_recommendation_flow.recommend_from_state(
        {"my_active": None, "opp_active": None},
        chart=TypeChart(),
        enumerate_actions=lambda *_args: [],
        opp_skill_source=lambda _opp: "none",
        predict_opponent=lambda *_args: [],
        score_action=lambda *_args: (0.0, "", {}),
        battle_metrics=lambda *_args: {},
    ) is None


def test_recommend_from_state_returns_none_without_actions_or_predictions():
    state = _state()

    assert engine_recommendation_flow.recommend_from_state(
        state,
        chart=TypeChart(),
        enumerate_actions=lambda *_args: [],
        opp_skill_source=lambda _opp: "none",
        predict_opponent=lambda *_args: [OpponentAction(action_type="skill", probability=1.0)],
        score_action=lambda *_args: (0.0, "", {}),
        battle_metrics=lambda *_args: {},
    ) is None
    assert engine_recommendation_flow.recommend_from_state(
        state,
        chart=TypeChart(),
        enumerate_actions=lambda *_args: [{"action_type": "skill", "skill_name": "强攻"}],
        opp_skill_source=lambda _opp: "none",
        predict_opponent=lambda *_args: [],
        score_action=lambda *_args: (0.0, "", {}),
        battle_metrics=lambda *_args: {},
    ) is None


def test_recommend_from_state_scores_actions_and_builds_recommendation():
    state = _state()
    calls = {"score": 0}

    def score_action(action, my_active, opp_active, my_pets, opp_pets, opp_predicted, flow_state, top_threat_name):
        calls["score"] += 1
        assert action["skill_name"] == "强攻"
        assert my_active is state["my_active"]
        assert opp_active is state["opp_active"]
        assert my_pets == state["my_pets"]
        assert opp_pets == state["opp_pets"]
        assert len(opp_predicted) == 1
        assert flow_state is state
        assert top_threat_name == "敌方"
        return 0.5, "强攻：50 伤害", {"expected_gain": "压血"}

    rec = engine_recommendation_flow.recommend_from_state(
        state,
        chart=TypeChart(),
        enumerate_actions=lambda *_args: [{"action_type": "skill", "skill_name": "强攻"}],
        opp_skill_source=lambda _opp: "used",
        predict_opponent=lambda *_args: [OpponentAction(action_type="skill", probability=1.0)],
        score_action=score_action,
        battle_metrics=lambda *_args: {"type_matchup": 1.0},
    )

    assert calls["score"] == 1
    assert rec is not None
    assert rec.round_number == 3
    assert rec.actions[0].skill_name == "强攻"
    assert rec.metrics == {"type_matchup": 1.0}
