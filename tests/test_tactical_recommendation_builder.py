"""TacticalRecommendation 组装测试。"""
from __future__ import annotations

from src.analysis.models import ActionScore, OpponentAction
from src.analysis.tactical import recommendation_builder, recommendations


def _inputs():
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
    return scored, opp_predicted, my_active, opp_active


def test_build_recommendation_assembles_contract_fields():
    scored, opp_predicted, my_active, opp_active = _inputs()

    rec = recommendation_builder.build_recommendation(
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


def test_recommendations_builder_facade_stays_compatible():
    scored, opp_predicted, my_active, opp_active = _inputs()

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
