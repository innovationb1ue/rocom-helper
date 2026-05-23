"""HookSignal 协同机制测试。"""
from __future__ import annotations

import pytest

from src.analysis.hook_registry import HookContext, HookSignal, HookTrigger
from src.analysis.hooks.switch_advisor import SwitchAdvisorHook
from src.analysis.hooks.energy_monitor import EnergyMonitorHook
from src.analysis.tactical_engine import TacticalEngine
from src.game.type_chart import TypeChart


def _make_pet(
    name="测试宠",
    hp=300,
    max_hp=300,
    energy=8,
    types=None,
    speed=100,
    equipped_skills=None,
    pet_id=1,
):
    if types is None:
        types = [1]
    if equipped_skills is None:
        equipped_skills = [
            {"skill_id": 7020370, "skill_name": "撞击", "equipped_slot": 0,
             "skill_damage_type": 2, "skill_element": 1, "cost_energy": 1},
        ]
    return {
        "name": name,
        "pet_id": pet_id,
        "current_hp": hp,
        "max_hp": max_hp,
        "hp_pct": hp / max_hp,
        "energy": energy,
        "types": types,
        "base_speed": speed,
        "effective_speed": speed,
        "stats": [
            {"name": "HP", "total": max_hp},
            {"name": "ATK", "total": 80},
            {"name": "DEF", "total": 70},
            {"name": "SPATK", "total": 80},
            {"name": "SPDEF", "total": 70},
            {"name": "SPEED", "total": speed},
        ],
        "buffs": [],
        "equipped_skills": equipped_skills,
        "used_skills": [],
        "level": 50,
    }


def _make_state(
    my_active=None,
    opp_active=None,
    my_pets=None,
    opp_pets=None,
    round_num=1,
    hook_signals=None,
):
    if my_active is None:
        my_active = _make_pet("我方宠", pet_id=1)
    if opp_active is None:
        opp_active = _make_pet("敌方宠", pet_id=101)
    if my_pets is None:
        my_pets = [my_active]
    if opp_pets is None:
        opp_pets = [opp_active]
    state = {
        "battle_id": 1,
        "round": round_num,
        "phase": "selecting",
        "my_active": my_active,
        "opp_active": opp_active,
        "my_pets": my_pets,
        "opp_pets": opp_pets,
        "weather": None,
        "result": None,
    }
    if hook_signals is not None:
        state["_hook_signals"] = hook_signals
    return state


class TestSwitchAdvisorSignals:
    def test_bad_matchup_emits_prefer_switch(self):
        hook = SwitchAdvisorHook(TypeChart())
        my_active = _make_pet("草龟", types=[3], pet_id=1)
        opp_active = _make_pet("火龙", types=[1], pet_id=101)
        my_pets = [my_active, _make_pet("水龟", types=[2], pet_id=2)]
        ctx = HookContext(
            opcode=0x131A,
            detail={},
            state={
                "my_active": my_active,
                "opp_active": opp_active,
                "my_pets": my_pets,
                "round": 1,
            },
            round_num=1,
        )
        signals = hook.emit_signals(ctx)
        assert len(signals) == 1
        assert signals[0].signal_type == "prefer_switch"
        assert signals[0].target == "水龟"
        assert signals[0].strength == 0.8

    def test_good_matchup_emits_no_signal(self):
        hook = SwitchAdvisorHook(TypeChart())
        my_active = _make_pet("水龟", types=[2], pet_id=1)
        opp_active = _make_pet("火龙", types=[1], pet_id=101)
        my_pets = [my_active]
        ctx = HookContext(
            opcode=0x131A,
            detail={},
            state={
                "my_active": my_active,
                "opp_active": opp_active,
                "my_pets": my_pets,
                "round": 1,
            },
            round_num=1,
        )
        signals = hook.emit_signals(ctx)
        assert len(signals) == 0


class TestEnergyMonitorSignals:
    def test_energy_starved_emits_avoid_skill(self):
        hook = EnergyMonitorHook()
        my_active = _make_pet(
            "我方",
            energy=1,
            equipped_skills=[
                {"skill_id": 1, "skill_name": "强击", "cost_energy": 3,
                 "skill_damage_type": 2},
            ],
        )
        ctx = HookContext(
            opcode=0x131A,
            detail={},
            state={"my_active": my_active, "opp_active": None, "round": 1},
            round_num=1,
        )
        signals = hook.emit_signals(ctx)
        assert len(signals) == 1
        assert signals[0].signal_type == "avoid_skill"
        assert signals[0].strength == 0.9

    def test_sufficient_energy_emits_no_signal(self):
        hook = EnergyMonitorHook()
        my_active = _make_pet("我方", energy=8)
        ctx = HookContext(
            opcode=0x131A,
            detail={},
            state={"my_active": my_active, "opp_active": None, "round": 1},
            round_num=1,
        )
        signals = hook.emit_signals(ctx)
        assert len(signals) == 0


class TestTacticalEngineSignalModifiers:
    def test_prefer_switch_boosts_switch_score(self):
        my = _make_pet("我方", pet_id=1, energy=10)
        alt = _make_pet("替补", pet_id=2, hp=250, max_hp=300, types=[2])
        opp = _make_pet("敌方", pet_id=101, types=[1])
        state = _make_state(my_active=my, opp_active=opp, my_pets=[my, alt])
        engine = TacticalEngine()

        rec_no_signal = engine.recommend(state)
        switch_score_no = next(
            a.score for a in rec_no_signal.actions if a.action_type == "switch"
        )

        state["_hook_signals"] = [
            {
                "hook_id": "switch_advisor",
                "signal_type": "prefer_switch",
                "target": "替补",
                "strength": 0.8,
            }
        ]
        rec_signal = engine.recommend(state)
        switch_score_yes = next(
            a.score for a in rec_signal.actions if a.action_type == "switch"
        )

        assert switch_score_yes > switch_score_no

    def test_avoid_skill_reduces_high_cost_skill_score(self):
        engine = TacticalEngine()
        my_active = _make_pet("我方", pet_id=1, energy=10)
        opp_active = _make_pet("敌方", pet_id=101)

        high_cost_action = {
            "action_type": "skill",
            "skill_id": 1,
            "skill_name": "高耗",
            "energy_cost": 5,
            "damage_type": 2,
            "skill_element": 1,
            "meta": {"damage_type": 2, "dam_para": [65]},
            "is_damage_skill": True,
        }

        opp_predicted = engine._predict_opp_actions(
            opp_active, [opp_active], _make_state(),
        )
        assert opp_predicted
        state = _make_state(my_active=my_active, opp_active=opp_active)

        score_no, _, _ = engine._score_action(
            high_cost_action, my_active, opp_active,
            [my_active], [opp_active], opp_predicted, state,
        )

        state["_hook_signals"] = [
            {
                "hook_id": "energy_monitor",
                "signal_type": "avoid_skill",
                "target": None,
                "strength": 0.9,
            }
        ]
        score_yes, _, _ = engine._score_action(
            high_cost_action, my_active, opp_active,
            [my_active], [opp_active], opp_predicted, state,
        )

        assert score_yes < score_no
