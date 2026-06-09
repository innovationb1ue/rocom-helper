"""非伤害技能战术评分测试。"""
from __future__ import annotations

from src.analysis.tactical import non_damage_scoring


def _pet(name="宠", hp=300, max_hp=300, energy=10, speed=100, buffs=None):
    return {
        "name": name,
        "current_hp": hp,
        "max_hp": max_hp,
        "hp_pct": hp / max_hp,
        "energy": energy,
        "base_speed": speed,
        "effective_speed": speed,
        "buffs": buffs or [],
    }


def _confidence(_opp):
    return "high"


def test_score_non_damage_skill_builds_setup_detail():
    my = _pet("我方", hp=120, max_hp=300, energy=8)
    opp = _pet("敌方")
    action = {
        "action_type": "skill",
        "skill_name": "防御",
        "energy_cost": 1,
        "meta": {"desc": "提升防御并回复"},
    }

    score, reason, detail = non_damage_scoring.score_non_damage_skill(
        action,
        my,
        opp,
        assess_confidence=_confidence,
    )

    assert score >= 0.05
    assert "防御" in reason
    assert detail["can_ko"] is False
    assert detail["metrics"]["energy_after"] == 7
    assert detail["category"] in {"setup", "conservative"}


def test_score_non_damage_skill_rewards_cleanse_when_negative_buff_exists():
    action = {
        "action_type": "skill",
        "skill_name": "净化",
        "energy_cost": 0,
        "meta": {"desc": "净化自身异常并解除弱化"},
    }
    clean = _pet("我方")
    debuffed = _pet("我方", buffs=[{"stage": -1}])
    opp = _pet("敌方")

    clean_score, _, _ = non_damage_scoring.score_non_damage_skill(
        action,
        clean,
        opp,
        assess_confidence=_confidence,
    )
    debuffed_score, _, _ = non_damage_scoring.score_non_damage_skill(
        action,
        debuffed,
        opp,
        assess_confidence=_confidence,
    )

    assert debuffed_score >= clean_score


def test_score_non_damage_skill_applies_energy_floor():
    action = {
        "action_type": "skill",
        "skill_name": "昂贵辅助",
        "energy_cost": 99,
        "meta": {"desc": "强化"},
    }

    score, _reason, detail = non_damage_scoring.score_non_damage_skill(
        action,
        _pet("我方", energy=3),
        _pet("敌方"),
        assess_confidence=_confidence,
    )

    assert score == 0.05
    assert detail["metrics"]["energy_after"] == 0
