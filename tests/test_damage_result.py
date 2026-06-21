"""伤害结果模型和结果辅助函数测试。"""
from __future__ import annotations

from src.analysis.damage.result import (
    DamageResult,
    base_hit_count,
    collect_derived_buffs,
    damage_result_from_dict,
    skill_power,
)
from src.analysis.damage_calc import DamageResult as CompatDamageResult


def _result(**overrides) -> DamageResult:
    data = {
        "skill_id": 1,
        "skill_name": "测试技能",
        "power": 80,
        "effective_power": 120,
        "damage_type": 2,
        "skill_element": 1,
        "skill_element_name": "火",
        "effectiveness": 1.0,
        "effectiveness_label": "普通",
        "is_stab": True,
        "expected_damage": 42,
        "pct_hp": 0.21,
        "can_ko": False,
        "energy_cost": 2,
        "confidence": "high",
        "hit_count": 2,
        "damage_breakdown": {"defender_current_hp": 300},
        "warnings": [],
    }
    data.update(overrides)
    return DamageResult(**data)


def test_damage_calc_re_exports_result_for_backward_compatibility():
    assert CompatDamageResult is DamageResult


def test_damage_result_to_dict_keeps_computed_compatibility_fields():
    result = _result()

    data = result.to_dict()

    assert data["min_damage"] == 42
    assert data["max_damage"] == 42
    assert data["total_damage"] == 84
    assert data["total_min_damage"] == 84
    assert data["total_max_damage"] == 84
    assert data["pct_hp_range"] == (0.21, 0.21)


def test_damage_result_from_dict_ignores_computed_fields():
    result = damage_result_from_dict({
        **_result().to_dict(),
        "unknown_field": "ignored",
    })

    assert isinstance(result, DamageResult)
    assert result.expected_damage == 42
    assert result.total_damage == 84


def test_collect_derived_buffs_flattens_children_with_parent_identity():
    derived = collect_derived_buffs([
        {
            "id": 20890020,
            "name": "反射护盾",
            "derived_buffs": [{"id": 20171910, "name": "魔攻提升"}, 20171911],
        },
        "invalid",
    ])

    assert derived == [
        {
            "id": 20171910,
            "name": "魔攻提升",
            "parent_buff_id": 20890020,
            "parent_buff_name": "反射护盾",
        },
        {
            "id": 20171911,
            "parent_buff_id": 20890020,
            "parent_buff_name": "反射护盾",
        },
    ]


def test_base_hit_count_parses_combo_desc_and_defaults_to_one():
    assert base_hit_count({"desc": "造成物伤，3连击。"}) == 3
    assert base_hit_count({"desc": "造成物伤。"}) == 1
    assert base_hit_count({}) == 1


def test_skill_power_reads_first_damage_parameter():
    assert skill_power({"dam_para": [90, 1]}) == 90
    assert skill_power({"dam_para": []}) == 0
    assert skill_power({}) == 0
