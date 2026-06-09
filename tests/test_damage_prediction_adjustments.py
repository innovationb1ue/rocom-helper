"""伤害预测结果调整规则测试。"""
from __future__ import annotations

from src.analysis.damage.prediction_adjustments import apply_calibration, apply_special_rule
from src.analysis.damage.prediction_config import DamageCalibration, SpecialDamageRule
from src.analysis.damage.result import DamageResult


def _result(**overrides) -> DamageResult:
    data = {
        "skill_id": 900001,
        "skill_name": "测试伤害",
        "power": 80,
        "effective_power": 80,
        "damage_type": 2,
        "skill_element": 1,
        "skill_element_name": "火",
        "effectiveness": 1.0,
        "effectiveness_label": "普通",
        "is_stab": False,
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
            "special_damage_rule": None,
        },
        "warnings": [],
    }
    data.update(overrides)
    return DamageResult(**data)


def test_apply_special_rule_returns_original_without_marker():
    dr = _result()

    assert apply_special_rule(dr, SpecialDamageRule(mode="fixed", per_hit=10, hit_count=2)) is dr


def test_apply_special_rule_marks_missing_config_as_low_confidence():
    dr = _result(damage_breakdown={
        "defender_current_hp": 300,
        "defender_max_hp": 300,
        "special_damage_rule": {"mode": "fixed", "source": "config_missing"},
    })

    adjusted = apply_special_rule(dr, SpecialDamageRule())

    assert adjusted.confidence == "low"
    assert adjusted.expected_damage == 40
    assert adjusted.damage_breakdown["special_damage_rule"]["source"] == "config_missing"


def test_apply_special_rule_replaces_damage_when_config_present():
    dr = _result(damage_breakdown={
        "defender_current_hp": 35,
        "defender_max_hp": 100,
        "special_damage_rule": {"mode": "fixed", "source": "config_missing"},
    })

    adjusted = apply_special_rule(
        dr,
        SpecialDamageRule(mode="fixed", per_hit=12, hit_count=3, key="900001"),
    )

    assert adjusted.expected_damage == 12
    assert adjusted.hit_count == 3
    assert adjusted.total_damage == 36
    assert adjusted.pct_hp == 0.36
    assert adjusted.can_ko is True
    assert adjusted.damage_breakdown["special_damage_rule"]["source"] == "config"


def test_apply_calibration_returns_original_without_active_multiplier():
    dr = _result()

    assert apply_calibration(dr, DamageCalibration()) is dr
    assert apply_calibration(dr, DamageCalibration(multiplier=1.0, key="900001")) is dr


def test_apply_calibration_adjusts_damage_and_records_raw_value():
    dr = _result(damage_breakdown={
        "defender_current_hp": 55,
        "defender_max_hp": 100,
        "special_damage_rule": None,
    })

    adjusted = apply_calibration(dr, DamageCalibration(multiplier=1.5, key="900001"))

    assert adjusted.expected_damage == 60
    assert adjusted.pct_hp == 0.6
    assert adjusted.can_ko is True
    assert adjusted.damage_breakdown["raw_expected_damage"] == 40
    assert adjusted.damage_breakdown["calibration_mult"] == 1.5
