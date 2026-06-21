"""伤害预测输出变换测试。"""
from __future__ import annotations

from src.analysis.damage.prediction_config import DamageCalibration, SpecialDamageRule
from src.analysis.damage.prediction_output import (
    accuracy_flags,
    apply_calibration,
    apply_special_rule,
    audit_key,
    build_prediction_payload,
    secondary_effects,
    validation_hint,
)
from src.analysis.damage_calc import DamageResult


def _result(**overrides) -> DamageResult:
    data = {
        "skill_id": 900001,
        "skill_name": "测试伤害",
        "power": 80,
        "effective_power": 120,
        "damage_type": 2,
        "skill_element": 1,
        "skill_element_name": "火",
        "effectiveness": 1.0,
        "effectiveness_label": "普通",
        "is_stab": True,
        "expected_damage": 40,
        "pct_hp": 0.2,
        "can_ko": False,
        "energy_cost": 2,
        "confidence": "high",
        "hit_count": 1,
        "power_mult": 1.0,
        "weather_mult": 1.0,
        "damage_breakdown": {
            "defender_current_hp": 300,
            "defender_max_hp": 300,
            "stat_sources": {"attack": "total", "defense": "total"},
            "runtime_sources": {},
            "special_damage_rule": None,
        },
        "warnings": [],
    }
    data.update(overrides)
    return DamageResult(**data)


def test_apply_calibration_adjusts_per_hit_and_keeps_raw_damage():
    adjusted = apply_calibration(_result(), DamageCalibration(multiplier=1.5, key="900001"))

    assert adjusted.expected_damage == 60
    assert adjusted.damage_breakdown["raw_expected_damage"] == 40
    assert adjusted.damage_breakdown["calibration_mult"] == 1.5


def test_apply_special_rule_replaces_fixed_damage_when_marker_exists():
    dr = _result(damage_breakdown={
        "defender_current_hp": 300,
        "defender_max_hp": 300,
        "stat_sources": {},
        "runtime_sources": {},
        "special_damage_rule": {"mode": "special_fixed_light_multihit", "source": "config_missing"},
    })

    adjusted = apply_special_rule(
        dr,
        SpecialDamageRule(mode="special_fixed_light_multihit", hit_count=4, per_hit=12, key="7060130"),
    )

    assert adjusted.expected_damage == 12
    assert adjusted.hit_count == 4
    assert adjusted.total_damage == 48
    assert adjusted.damage_breakdown["special_damage_rule"]["source"] == "config"


def test_accuracy_flags_and_validation_hint_include_runtime_effects():
    dr = _result(damage_breakdown={
        "defender_current_hp": 300,
        "defender_max_hp": 300,
        "stat_sources": {"attack": "wiki", "defense": "total"},
        "runtime_sources": {"has_set_cost_info": True},
        "special_damage_rule": None,
    })

    flags = accuracy_flags(dr, DamageCalibration())

    assert "estimated_stats" in flags
    assert "runtime_effect_unmodeled" in flags
    assert "uncalibrated_skill" in flags
    assert "攻防属性来自估算" in (validation_hint(flags) or "")


def test_secondary_effects_models_poison_capsule_tick():
    dr = _result(skill_id=7120090, expected_damage=30)

    effects = secondary_effects(dr, {"types": [1], "current_hp": 300, "max_hp": 300})

    assert effects[0]["kind"] == "poison_tick"
    assert effects[0]["damage"] == 9


def test_build_prediction_payload_preserves_expected_contract():
    dr = _result()

    payload = build_prediction_payload(
        dr,
        {"name": "敌方", "current_hp": 300, "max_hp": 300},
        DamageCalibration(),
        SpecialDamageRule(),
    )

    assert payload["result"] is dr
    assert payload["prediction"]["audit_key"] == "900001:敌方"
    assert payload["prediction"]["total"] == 40
    assert payload["prediction"]["predicted_hp_after"] == 260
    assert payload["prediction"]["confidence"] == "medium"
    assert payload["explain"]["stat_sources"]["attack"] == "total"


def test_audit_key_prefers_battle_uid_then_pet_identity():
    dr = _result()

    assert audit_key(dr, {"battle_uid": "b1", "pet_id": 2}) == "900001:b1"
    assert audit_key(dr, {"pet_id": 2}) == "900001:2"
