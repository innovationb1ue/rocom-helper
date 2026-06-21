"""战术行动 detail 构造测试。"""
from __future__ import annotations

from src.analysis.tactical import action_detail_builder, action_outcome_scoring


def _pet(name="宠", hp=300, max_hp=300, energy=10, speed=100, stats=None):
    return {
        "name": name,
        "current_hp": hp,
        "max_hp": max_hp,
        "hp_pct": hp / max_hp,
        "energy": energy,
        "base_speed": speed,
        "effective_speed": speed,
        "stats": stats if stats is not None else {"atk": 100, "def": 100, "matk": 100, "mdef": 100},
        "equipped_skills": [{"skill_id": 1, "skill_name": "已知技能"}],
    }


def _action():
    return {
        "action_type": "skill",
        "skill_name": "强攻",
        "energy_cost": 2,
        "is_damage_skill": True,
        "meta": {"damage_type": 2, "dam_para": [100]},
    }


def _confidence(_opp):
    return "high"


def test_build_action_detail_preserves_frontend_contract_fields():
    my = _pet("我方", hp=240, energy=8, speed=120)
    opp = _pet("敌方", hp=180, max_hp=300, speed=80)
    outcome = action_outcome_scoring.ActionOutcomeScore(
        total_score=0.4,
        best_damage_dealt=90,
        worst_damage_taken=40,
        can_ko=False,
        display_damage_dealt=100,
        display_can_ko=False,
    )

    detail = action_detail_builder.build_action_detail(
        _action(),
        my,
        opp,
        {"weather": None},
        outcome,
        0.4,
        type_matchup_score=lambda *_args: 2.0,
        assess_confidence=_confidence,
    )

    assert detail["damage_dealt"] == 100
    assert detail["damage_taken"] == 40
    assert detail["can_ko"] is False
    assert detail["category"] == "pressure"
    assert "expected_gain" in detail
    assert "risk" in detail
    assert detail["confidence"] == "high"
    assert detail["metrics"]["energy_after"] == 6
    assert detail["metrics"]["type_matchup"] == 2.0
    assert detail["unknowns"] == []


def test_build_action_detail_marks_unknowns_and_low_confidence():
    my = _pet("我方")
    opp = _pet("敌方", stats={})
    opp["equipped_skills"] = []
    outcome = action_outcome_scoring.ActionOutcomeScore(
        total_score=0.1,
        best_damage_dealt=0,
        worst_damage_taken=0,
        can_ko=False,
        display_damage_dealt=None,
        display_can_ko=False,
    )

    detail = action_detail_builder.build_action_detail(
        _action(),
        my,
        opp,
        {},
        outcome,
        0.1,
        type_matchup_score=lambda *_args: 1.0,
        assess_confidence=_confidence,
    )

    assert detail["damage_dealt"] is None
    assert detail["damage_taken"] is None
    assert len(detail["unknowns"]) >= 2
    assert detail["confidence"] == "low"


def test_display_damage_hides_zero_or_missing_preview():
    assert action_detail_builder.display_damage(
        action_outcome_scoring.ActionOutcomeScore(0.0, 50, 0, False, 0, False)
    ) is None
    assert action_detail_builder.display_damage(
        action_outcome_scoring.ActionOutcomeScore(0.0, 50, 0, False, None, False)
    ) is None
