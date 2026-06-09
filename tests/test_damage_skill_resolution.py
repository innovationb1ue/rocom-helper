"""伤害技能输入解析辅助测试。"""
from __future__ import annotations

from src.analysis.damage import skill_resolution


def test_resolve_skill_element_maps_protocol_damage_type():
    assert skill_resolution.resolve_skill_element({"skill_dam_type": 5}) == 2


def test_resolve_skill_element_keeps_unknown_raw_value():
    assert skill_resolution.resolve_skill_element({"skill_dam_type": 999}) == 999


def test_is_attack_skill_requires_power_and_attack_damage_type():
    assert skill_resolution.is_attack_skill(80, 2) is True
    assert skill_resolution.is_attack_skill(80, 3) is True
    assert skill_resolution.is_attack_skill(0, 2) is False
    assert skill_resolution.is_attack_skill(80, 1) is False


def test_apply_buff_power_modifiers_respects_element_filter():
    attacker = {"buffs": [{"id": 20171870, "name": "普通加威力"}]}

    assert skill_resolution.apply_buff_power_modifiers(
        80,
        attacker,
        skill_element=0,
        skill_name="撞击",
    ) == 100
    assert skill_resolution.apply_buff_power_modifiers(
        80,
        attacker,
        skill_element=17,
        skill_name="光系技能",
    ) == 80
