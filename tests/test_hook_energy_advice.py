"""energy_advice helper 测试 — 能量监控规则可独立验证。"""
from __future__ import annotations

from src.analysis.hooks.energy_advice import (
    build_my_energy_messages,
    build_opp_energy_messages,
    energy_advice_priority,
    equipped_or_used_skills,
    min_attack_cost,
    should_avoid_skill,
)


def test_min_attack_cost_uses_only_attack_skills():
    skills = [
        {"skill_name": "变化", "skill_damage_type": 1, "cost_energy": 1},
        {"skill_name": "强击", "skill_damage_type": 2, "cost_energy": 4},
        {"skill_name": "快攻", "skill_damage_type": 3, "cost_energy": 2},
        {"skill_name": "无消耗字段", "skill_damage_type": 2},
    ]

    assert min_attack_cost(skills) == 2
    assert min_attack_cost([{"skill_damage_type": 1, "cost_energy": 1}]) == 0


def test_equipped_or_used_skills_keeps_legacy_fallback_order():
    equipped = [{"skill_name": "装备技能"}]
    used = [{"skill_name": "已用技能"}]

    assert equipped_or_used_skills({"equipped_skills": equipped, "used_skills": used}) is equipped
    assert equipped_or_used_skills({"equipped_skills": [], "used_skills": used}) is used
    assert equipped_or_used_skills({}) == []


def test_build_my_energy_messages_warns_starved_and_low_energy():
    starved = build_my_energy_messages({
        "energy": 1,
        "equipped_skills": [{"skill_damage_type": 2, "cost_energy": 3}],
    })
    low = build_my_energy_messages({
        "energy": 2,
        "equipped_skills": [{"skill_damage_type": 2, "cost_energy": 3}],
    })
    enough = build_my_energy_messages({
        "energy": 3,
        "equipped_skills": [{"skill_damage_type": 2, "cost_energy": 2}],
    })

    assert starved[0]["type"] == "energy_starved"
    assert "无法" in starved[0]["message"]
    assert low[0]["type"] == "energy_low"
    assert enough == []


def test_build_opp_energy_messages_requires_drop_to_low_energy():
    assert build_opp_energy_messages({"energy": 2}, [
        {"round": 1, "energy": 5},
        {"round": 2, "energy": 2},
    ])[0]["type"] == "opp_energy_low"
    assert build_opp_energy_messages({"energy": 2}, [
        {"round": 1, "energy": 2},
        {"round": 2, "energy": 2},
    ]) == []
    assert build_opp_energy_messages({"energy": 3}, [
        {"round": 1, "energy": 5},
        {"round": 2, "energy": 3},
    ]) == []


def test_energy_priority_and_avoid_signal_rules():
    assert energy_advice_priority([{"type": "energy_starved"}]) == 1
    assert energy_advice_priority([{"type": "opp_energy_low"}]) == 2
    assert should_avoid_skill({
        "energy": 1,
        "equipped_skills": [{"skill_damage_type": 2, "cost_energy": 3}],
    }) is True
    assert should_avoid_skill({
        "energy": 2,
        "equipped_skills": [{"skill_damage_type": 2, "cost_energy": 3}],
    }) is False
