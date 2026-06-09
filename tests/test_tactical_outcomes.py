"""战术 outcome 推演测试。"""
from __future__ import annotations

from typing import Optional

from src.analysis.models import OpponentAction
from src.analysis.tactical import outcomes


def _pet(name="宠", hp=300, energy=10, speed=100):
    return {
        "name": name,
        "current_hp": hp,
        "max_hp": 300,
        "energy": energy,
        "base_speed": speed,
        "effective_speed": speed,
        "types": [1],
        "buffs": [],
    }


def _skill_action(**overrides):
    action = {
        "action_type": "skill",
        "skill_id": 1,
        "skill_name": "攻击",
        "energy_cost": 2,
        "priority_layer": 0,
        "meta": {"damage_type": 2},
    }
    action.update(overrides)
    return action


def _switch_action(incoming):
    return {
        "action_type": "switch",
        "switch_to_name": incoming["name"],
        "switch_to_pet": incoming,
        "energy_cost": 0,
    }


def _damage(attacker, _defender, skill_meta, _weather):
    if skill_meta is None:
        return 0
    return 120 if attacker.get("name") == "我方" else 80


def _matchup(_mine, _opp):
    return 2.0


def _target(_opp_action, opp_pets, _my_active) -> Optional[dict]:
    return next((pet for pet in opp_pets if pet["name"] == "替补敌"), None)


def test_skill_vs_skill_uses_priority_before_speed():
    my = _pet("我方", hp=50, speed=300)
    opp = _pet("敌方", hp=300, speed=100)
    outcome = outcomes.resolve_skill_vs_skill(
        _skill_action(priority_layer=0),
        OpponentAction(action_type="skill", skill_id=7020370, probability=1.0, priority_layer=1),
        my,
        opp,
        {"weather": None},
        None,
        calc_damage=_damage,
        type_matchup_score=_matchup,
    )

    assert outcome.we_act_first is False
    assert outcome.opp_kos_us is True
    assert outcome.our_damage_dealt == 120
    assert outcome.opp_remaining_hp == 300


def test_skill_vs_skill_prevents_counter_damage_after_ko():
    my = _pet("我方", hp=300, speed=300)
    opp = _pet("敌方", hp=100, speed=100)
    outcome = outcomes.resolve_skill_vs_skill(
        _skill_action(priority_layer=0),
        OpponentAction(action_type="skill", skill_id=7020370, probability=1.0, priority_layer=0),
        my,
        opp,
        {"weather": None},
        None,
        calc_damage=_damage,
        type_matchup_score=_matchup,
    )

    assert outcome.we_act_first is True
    assert outcome.we_ko is True
    assert outcome.opp_damage_dealt == 0
    assert outcome.pet_count_delta == 1


def test_switch_outcome_applies_incoming_damage_to_new_pet():
    my = _pet("我方")
    opp = _pet("敌方")
    incoming = _pet("替补", hp=70, energy=6)

    outcome = outcomes.resolve_switch_outcome(
        _switch_action(incoming),
        OpponentAction(action_type="skill", skill_id=7020370, probability=1.0),
        my,
        opp,
        {"weather": None},
        None,
        calc_damage=_damage,
        type_matchup_score=_matchup,
    )

    assert outcome.our_damage_dealt == 0
    assert outcome.opp_damage_dealt == 80
    assert outcome.opp_kos_us is True
    assert outcome.incoming_energy == 6
    assert outcome.pet_count_delta == -1


def test_opp_switch_outcome_uses_selected_switch_target():
    my = _pet("我方", hp=300)
    opp = _pet("敌方", hp=300)
    target = _pet("替补敌", hp=90)

    outcome = outcomes.resolve_opp_switch_outcome(
        _skill_action(),
        OpponentAction(action_type="switch", switch_to_name="替补敌", probability=1.0),
        my,
        opp,
        [opp, target],
        {"weather": None},
        None,
        calc_damage=_damage,
        type_matchup_score=_matchup,
        most_likely_switch_target=_target,
    )

    assert outcome.our_damage_dealt == 120
    assert outcome.we_ko is True
    assert outcome.opp_remaining_hp == 0
    assert outcome.pet_count_delta == 1


def test_resolve_outcome_dispatches_by_action_type():
    my = _pet("我方", hp=300)
    opp = _pet("敌方", hp=300)
    incoming = _pet("替补", hp=300)

    switch_result = outcomes.resolve_outcome(
        _switch_action(incoming),
        OpponentAction(action_type="skill", skill_id=7020370, probability=1.0),
        my,
        opp,
        [my, incoming],
        [opp],
        {"weather": None},
        calc_damage=_damage,
        type_matchup_score=_matchup,
        most_likely_switch_target=_target,
    )
    opp_switch_result = outcomes.resolve_outcome(
        _skill_action(),
        OpponentAction(action_type="switch", probability=1.0),
        my,
        opp,
        [my],
        [opp],
        {"weather": None},
        calc_damage=_damage,
        type_matchup_score=_matchup,
        most_likely_switch_target=lambda *_args: None,
    )

    assert switch_result.our_damage_dealt == 0
    assert opp_switch_result.opp_damage_dealt == 0
