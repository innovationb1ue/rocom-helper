"""战术行动评分聚合测试。"""
from __future__ import annotations

from src.analysis.models import OpponentAction, ResolvedOutcome
from src.analysis.tactical import action_scoring


def _pet(name="宠", hp=300, max_hp=300, energy=10, speed=100, types=None):
    return {
        "name": name,
        "current_hp": hp,
        "max_hp": max_hp,
        "hp_pct": hp / max_hp,
        "energy": energy,
        "base_speed": speed,
        "effective_speed": speed,
        "types": types or [1],
        "buffs": [],
    }


def _damage_action():
    return {
        "action_type": "skill",
        "skill_id": 1,
        "skill_name": "强攻",
        "energy_cost": 2,
        "is_damage_skill": True,
        "meta": {"damage_type": 2, "dam_para": [100]},
    }


def _resolve_outcome(
    _our_action,
    _opp_action,
    _my_active,
    _opp_active,
    _my_pets,
    _opp_pets,
    _state,
):
    return ResolvedOutcome(
        our_damage_dealt=80,
        opp_damage_dealt=30,
        we_ko=False,
        opp_kos_us=False,
        we_act_first=True,
        our_remaining_hp=270,
        opp_remaining_hp=120,
        type_matchup_after=2.0,
        energy_after=8,
        pet_count_delta=0,
    )


def _type_matchup(_mine, _opp):
    return 2.0


def _confidence(_opp):
    return "high"


def test_score_action_aggregates_outcomes_and_builds_detail():
    my = _pet("我方", hp=300)
    opp = _pet("敌方", hp=200)

    score, reason, detail = action_scoring.score_action(
        _damage_action(),
        my,
        opp,
        [my],
        [opp],
        [OpponentAction(action_type="skill", skill_id=2, probability=1.0)],
        {"weather": None},
        resolve_outcome=_resolve_outcome,
        calc_damage=lambda *_args: 90,
        type_matchup_score=_type_matchup,
        assess_confidence=_confidence,
    )

    assert score > 0
    assert "强攻" in reason
    assert detail["damage_dealt"] == 90
    assert detail["damage_taken"] == 30
    assert detail["metrics"]["type_matchup"] == 2.0
    assert detail["confidence"] == "low"


def test_hook_signal_modifiers_are_independent_from_engine():
    switch = {"action_type": "switch"}
    costly_skill = {"action_type": "skill", "energy_cost": 5}
    cheap_skill = {"action_type": "skill", "energy_cost": 1}

    assert action_scoring.apply_hook_signal_modifiers(
        1.0,
        switch,
        [{"signal_type": "prefer_switch"}],
    ) == 1.2
    assert action_scoring.apply_hook_signal_modifiers(
        1.0,
        costly_skill,
        [{"signal_type": "avoid_skill"}],
    ) == 0.5
    assert action_scoring.apply_hook_signal_modifiers(
        1.0,
        cheap_skill,
        [{"signal_type": "avoid_skill"}],
    ) == 0.8


def test_score_non_damage_skill_returns_setup_detail():
    my = _pet("我方", hp=120, max_hp=300, energy=8)
    opp = _pet("敌方")
    action = {
        "action_type": "skill",
        "skill_name": "防御",
        "energy_cost": 1,
        "meta": {"desc": "提升防御并回复"},
    }

    score, reason, detail = action_scoring.score_non_damage_skill(
        action,
        my,
        opp,
        assess_confidence=_confidence,
    )

    assert score >= 0.05
    assert "防御" in reason
    assert detail["can_ko"] is False
    assert "energy_after" in detail["metrics"]


def test_battle_metrics_keeps_cockpit_contract():
    my = _pet("我方", energy=7, speed=200)
    opp = _pet("敌方", energy=3, speed=100)
    dead = _pet("战败", hp=0)

    metrics = action_scoring.battle_metrics(
        my,
        opp,
        [my, dead],
        [opp],
        type_matchup_score=_type_matchup,
    )

    assert metrics["speed_line"]["order"] == "我方先手"
    assert metrics["energy_window"] == {"my": 7, "opp": 3}
    assert metrics["pet_count"]["delta"] == 0
    assert metrics["type_matchup"] == 2.0
