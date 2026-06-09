"""整条战术推荐展示测试。"""
from __future__ import annotations

from src.analysis.models import ActionScore, OpponentAction
from src.analysis.tactical import recommendation_presentation


def test_primary_plan_prefers_top_action_gain():
    actions = [ActionScore(action_type="skill", skill_name="终结技", expected_gain="本回合有击杀线")]

    assert recommendation_presentation.primary_plan(actions) == "首选 终结技：本回合有击杀线"
    assert recommendation_presentation.primary_plan([]) == ""


def test_build_warnings_reports_low_confidence_threat_and_gamble():
    warnings = recommendation_presentation.build_warnings(
        [ActionScore(action_type="skill", category="gamble")],
        [OpponentAction(action_type="skill", skill_name="反击", probability=1.0, can_ko=True)],
        confidence="low",
        opp_skill_source="preset",
    )

    assert any("技能信息不足" in warning for warning in warnings)
    assert any("击杀威胁" in warning for warning in warnings)
    assert any("高风险收益线" in warning for warning in warnings)


def test_opponent_profile_summarizes_revealed_skills_and_probabilities():
    profile = recommendation_presentation.opponent_profile(
        {
            "used_skills": [{"skill_id": 1, "skill_name": "反击"}],
            "hp_pct": 0.2,
            "energy": 1,
        },
        [
            OpponentAction(action_type="switch", probability=0.25),
            OpponentAction(action_type="skill", probability=0.75),
        ],
        "used",
    )

    assert profile["skill_source"] == "used"
    assert profile["revealed_skill_count"] == 1
    assert profile["estimated_switch_probability"] == 0.25
    assert profile["estimated_skill_probability"] == 0.75
    assert profile["low_hp"] is True
    assert profile["low_energy"] is True


def test_opp_action_reason_distinguishes_used_and_candidate_skills():
    opp = {"used_skills": [{"skill_id": 1}]}

    assert "已使用过" in recommendation_presentation.opp_action_reason(1, 0.5, opp)
    assert "候选技能池" in recommendation_presentation.opp_action_reason(2, 0.5, opp)
