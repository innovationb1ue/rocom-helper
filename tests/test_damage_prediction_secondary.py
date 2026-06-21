"""伤害预测附带二段效果规则测试。"""
from __future__ import annotations

from src.analysis.damage.prediction_secondary import secondary_effects
from src.analysis.damage.result import DamageResult


def _result(**overrides) -> DamageResult:
    data = {
        "skill_id": 7120090,
        "skill_name": "毒囊",
        "power": 80,
        "effective_power": 80,
        "damage_type": 2,
        "skill_element": 7,
        "skill_element_name": "毒",
        "effectiveness": 1.0,
        "effectiveness_label": "普通",
        "is_stab": False,
        "expected_damage": 30,
        "pct_hp": 0.1,
        "can_ko": False,
        "energy_cost": 2,
        "confidence": "medium",
        "hit_count": 1,
        "power_mult": 1.0,
        "weather_mult": 1.0,
        "damage_breakdown": {
            "defender_current_hp": 300,
            "defender_max_hp": 300,
        },
        "warnings": [],
    }
    data.update(overrides)
    return DamageResult(**data)


def test_secondary_effects_returns_poison_tick_for_poison_capsule():
    effects = secondary_effects(_result(), {"types": [1], "current_hp": 300, "max_hp": 300})

    assert effects == [{
        "kind": "poison_tick",
        "name": "中毒当回合结算",
        "damage": 9,
        "ratio": 0.03,
        "timing": "after_skill_damage",
        "audit_policy": "excluded_from_direct_damage",
        "notes": "毒囊先造成本体伤害，再施加中毒；中毒在当前回合额外结算一次。",
    }]


def test_secondary_effects_skips_non_poison_capsule_skill():
    dr = _result(skill_id=900001)

    assert secondary_effects(dr, {"types": [1], "current_hp": 300, "max_hp": 300}) == []


def test_secondary_effects_skips_poison_type_defender():
    assert secondary_effects(_result(), {"types": [7], "current_hp": 300, "max_hp": 300}) == []


def test_secondary_effects_skips_when_direct_damage_koes():
    dr = _result(expected_damage=300, damage_breakdown={
        "defender_current_hp": 300,
        "defender_max_hp": 300,
    })

    assert secondary_effects(dr, {"types": [1], "current_hp": 300, "max_hp": 300}) == []


def test_secondary_effects_caps_tick_at_remaining_hp():
    dr = _result(expected_damage=298, damage_breakdown={
        "defender_current_hp": 300,
        "defender_max_hp": 300,
    })

    effects = secondary_effects(dr, {"types": [1], "current_hp": 300, "max_hp": 300})

    assert effects[0]["damage"] == 2
