"""伤害预测质量标签和提示规则测试。"""
from __future__ import annotations

from src.analysis.damage.prediction_config import DamageCalibration
from src.analysis.damage.prediction_quality import (
    accuracy_flags,
    prediction_confidence,
    validation_hint,
)
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
            "stat_sources": {"attack": "total", "defense": "total"},
            "runtime_sources": {},
            "special_damage_rule": None,
        },
        "warnings": [],
    }
    data.update(overrides)
    return DamageResult(**data)


def test_accuracy_flags_reports_estimated_stats_runtime_and_calibration():
    dr = _result(
        damage_breakdown={
            "defender_current_hp": 300,
            "defender_max_hp": 300,
            "stat_sources": {"attack": "wiki", "defense": "total"},
            "runtime_sources": {"has_damage_params": True, "has_set_cost_info": True},
            "special_damage_rule": None,
        },
        warnings=["能量不足，无法使用"],
    )

    flags = accuracy_flags(dr, DamageCalibration(multiplier=1.2, key="900001"))

    assert flags == [
        "estimated_stats",
        "calibrated",
        "energy_insufficient",
        "runtime_target_unmatched",
        "runtime_effect_unmodeled",
    ]


def test_prediction_confidence_degrades_by_flag_severity():
    assert prediction_confidence("high", ["estimated_stats"]) == "low"
    assert prediction_confidence("high", ["uncalibrated_skill"]) == "medium"
    assert prediction_confidence("medium", ["runtime_effect_unmodeled"]) == "medium"
    assert prediction_confidence("high", ["calibrated"]) == "high"


def test_validation_hint_joins_known_flags_in_order():
    hint = validation_hint(["multi_hit", "runtime_effect_unmodeled", "unknown_flag"])

    assert hint == "多段/动态连击会放大预测误差；存在尚未建模的运行时技能效果"
