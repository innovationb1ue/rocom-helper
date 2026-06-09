"""战术推荐结果组装测试。"""
from __future__ import annotations

from src.analysis.models import ActionScore, OpponentAction
from src.analysis.tactical import recommendations


def test_assess_confidence_prefers_equipped_then_revealed_skills():
    assert recommendations.assess_confidence({"equipped_skills": [{"skill_id": 1}]}) == "high"
    assert recommendations.assess_confidence({"skills": [{"skill_id": 1}]}) == "high"
    assert recommendations.assess_confidence({"used_skills": [{"skill_id": 1}, {"skill_id": 2}, {"skill_id": 3}]}) == "high"
    assert recommendations.assess_confidence({"used_skills": [{"skill_id": 1}]}) == "medium"
    assert recommendations.assess_confidence({}) == "low"


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

    score = recommendations.action_score_from_detail(action, 0.123456, "撞击：80 伤害", detail)

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


def test_score_action_candidates_sorts_descending():
    actions = [
        {"action_type": "skill", "skill_id": 1, "skill_name": "低分", "energy_cost": 1},
        {"action_type": "skill", "skill_id": 2, "skill_name": "高分", "energy_cost": 1},
    ]

    def _score(action):
        score = 0.8 if action["skill_name"] == "高分" else 0.1
        return score, action["skill_name"], {}

    scored = recommendations.score_action_candidates(actions, score_action=_score)

    assert [action.skill_name for action in scored] == ["高分", "低分"]
    assert [action.score for action in scored] == [0.8, 0.1]


def test_build_recommendation_assembles_contract_fields():
    scored = [
        ActionScore(
            action_type="skill",
            skill_name="终结技",
            score=0.9,
            category="finisher",
            expected_gain="本回合有击杀线",
        )
    ]
    opp_predicted = [
        OpponentAction(action_type="skill", skill_name="反击", probability=1.0, can_ko=True)
    ]
    my_active = {"name": "我方", "types": [1], "energy": 5}
    opp_active = {"name": "敌方", "used_skills": [{"skill_id": 1, "skill_name": "反击"}]}

    rec = recommendations.build_recommendation(
        scored=scored,
        opp_predicted=opp_predicted,
        state={"round": 7},
        my_active=my_active,
        opp_active=opp_active,
        my_pets=[my_active],
        opp_pets=[opp_active],
        opp_skill_source="used",
        battle_metrics=lambda *_args: {"type_matchup": 1.0},
    )

    assert rec.round_number == 7
    assert rec.confidence == "medium"
    assert rec.primary_plan.startswith("首选 终结技")
    assert rec.metrics == {"type_matchup": 1.0}
    assert rec.opponent_profile["skill_source"] == "used"
    assert rec.opponent_profile["revealed_skill_count"] == 1
    assert any("击杀威胁" in warning for warning in rec.warnings)
