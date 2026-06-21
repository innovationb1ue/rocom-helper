"""ActionScore 构造和排序测试。"""
from __future__ import annotations

from src.analysis.tactical import action_score_factory, recommendations


def test_action_score_from_detail_preserves_frontend_fields():
    action = {
        "action_type": "skill",
        "skill_id": 7020370,
        "skill_name": "撞击",
        "energy_cost": 2,
    }
    detail = {
        "category": "pressure",
        "expected_gain": "压血",
        "risk": "承伤",
        "confidence": "high",
        "damage_dealt": 80,
        "damage_taken": 20,
        "can_ko": True,
        "metrics": {"energy_after": 6},
        "unknowns": ["对手技能未知"],
    }

    score = action_score_factory.action_score_from_detail(action, 0.123456, "撞击：80 伤害", detail)

    assert score.action_type == "skill"
    assert score.skill_id == 7020370
    assert score.skill_name == "撞击"
    assert score.score == 0.1235
    assert score.reason == "撞击：80 伤害"
    assert score.category == "pressure"
    assert score.expected_gain == "压血"
    assert score.risk == "承伤"
    assert score.confidence == "high"
    assert score.damage_dealt == 80
    assert score.damage_taken == 20
    assert score.can_ko is True
    assert score.energy_cost == 2
    assert score.metrics["energy_after"] == 6
    assert score.unknowns == ["对手技能未知"]


def test_score_action_candidates_sorts_descending_and_facade_matches():
    actions = [
        {"action_type": "skill", "skill_id": 1, "skill_name": "低分", "energy_cost": 1},
        {"action_type": "skill", "skill_id": 2, "skill_name": "高分", "energy_cost": 1},
    ]

    def _score(action):
        score = 0.8 if action["skill_name"] == "高分" else 0.1
        return score, action["skill_name"], {}

    scored = action_score_factory.score_action_candidates(actions, score_action=_score)
    facade_scored = recommendations.score_action_candidates(actions, score_action=_score)

    assert [action.skill_name for action in scored] == ["高分", "低分"]
    assert [action.score for action in scored] == [0.8, 0.1]
    assert [action.skill_name for action in facade_scored] == ["高分", "低分"]
