"""战术行动 detail 构造测试。"""
from __future__ import annotations

from src.analysis.tactical import action_details, action_scoring


def _pet(name="宠", hp=300, max_hp=300, energy=10, speed=100):
    return {
        "name": name,
        "current_hp": hp,
        "max_hp": max_hp,
        "energy": energy,
        "base_speed": speed,
        "effective_speed": speed,
        "types": [1],
    }


def _type_matchup(_mine, _opp):
    return 2.0


def test_generate_reason_for_switch_and_skill():
    assert action_details.generate_reason(
        {"action_type": "switch", "switch_to_name": "海豹船长"},
        damage_dealt=0,
        damage_taken=42,
        can_ko=False,
    ) == "换上 海豹船长，吃 42 伤害，改善对位"

    assert action_details.generate_reason(
        {"action_type": "skill", "skill_name": "强攻", "energy_cost": 5},
        damage_dealt=180,
        damage_taken=30,
        can_ko=True,
    ) == "强攻：先手击杀，高伤害，耗能 5，承受 30"


def test_action_metrics_keeps_cockpit_contract_and_compat_facade():
    my = _pet("我方", hp=240, max_hp=300, energy=6, speed=120)
    opp = _pet("敌方", hp=100, max_hp=200, speed=150)
    action = {"action_type": "skill", "energy_cost": 2, "priority_layer": 1}

    expected = {
        "speed_order": "先手技能 +1",
        "my_speed": 120,
        "opp_speed": 150,
        "priority_layer": 1,
        "energy_after": 4,
        "kill_line": 10,
        "survival_line": 210,
        "damage_pct": 0.45,
        "incoming_pct": 0.1,
        "can_ko": False,
        "switch_penalty": False,
        "type_matchup": 2.0,
    }

    assert action_details.action_metrics(
        our_action=action,
        my_active=my,
        opp_active=opp,
        damage_dealt=90,
        damage_taken=30,
        can_ko=False,
        type_matchup_score=_type_matchup,
    ) == expected
    assert action_scoring.action_metrics(
        our_action=action,
        my_active=my,
        opp_active=opp,
        damage_dealt=90,
        damage_taken=30,
        can_ko=False,
        type_matchup_score=_type_matchup,
    ) == expected


def test_battle_metrics_keeps_cockpit_contract():
    my = _pet("我方", energy=7, speed=200)
    opp = _pet("敌方", energy=3, speed=100)
    dead = _pet("战败", hp=0)

    assert action_details.battle_metrics(
        my,
        opp,
        [my, dead],
        [opp],
        type_matchup_score=_type_matchup,
    ) == {
        "speed_line": {"my": 200, "opp": 100, "order": "我方先手"},
        "energy_window": {"my": 7, "opp": 3},
        "pet_count": {"my_alive": 1, "opp_alive": 1, "delta": 0},
        "type_matchup": 2.0,
    }
