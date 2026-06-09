"""伤害预测顶层 payload 组装测试。"""
from __future__ import annotations

from src.analysis.damage.prediction_config import DamageCalibration, SpecialDamageRule
from src.analysis.damage.prediction_payload import build_prediction_payload
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
        "confidence": "high",
        "hit_count": 1,
        "power_mult": 1.0,
        "weather_mult": 1.0,
        "damage_breakdown": {
            "defender_current_hp": 300,
            "defender_max_hp": 300,
            "stat_sources": {"attack": "total", "defense": "wiki"},
            "runtime_sources": {"has_set_cost_info": True},
            "special_damage_rule": None,
        },
        "warnings": [],
    }
    data.update(overrides)
    return DamageResult(**data)


def test_build_prediction_payload_preserves_frontend_contract_fields():
    dr = _result()

    payload = build_prediction_payload(
        dr,
        {"name": "敌方", "types": [1], "current_hp": 300, "max_hp": 300},
        DamageCalibration(),
        SpecialDamageRule(),
    )

    assert payload["result"] is dr
    assert payload["prediction"]["audit_key"] == "7120090:敌方"
    assert payload["prediction"]["per_hit"] == 30
    assert payload["prediction"]["total"] == 30
    assert payload["prediction"]["hit_count"] == 1
    assert payload["prediction"]["target_hp_before"] == 300
    assert payload["prediction"]["predicted_hp_after"] == 270
    assert payload["prediction"]["secondary_total"] == 9
    assert payload["prediction"]["tactical_total"] == 39
    assert payload["prediction"]["predicted_hp_after_with_secondary"] == 261
    assert payload["prediction"]["secondary_effects"][0]["kind"] == "poison_tick"
    assert payload["prediction"]["runtime_sources"] == {"has_set_cost_info": True}
    assert payload["prediction"]["confidence"] == "low"
    assert payload["prediction"]["accuracy_flags"] == [
        "estimated_stats",
        "uncalibrated_skill",
        "runtime_effect_unmodeled",
    ]
    assert "攻防属性来自估算" in payload["validation_hint"]
    assert payload["explain"]["secondary_effects"] == payload["prediction"]["secondary_effects"]


def test_build_prediction_payload_uses_calibration_for_confidence_and_hint():
    payload = build_prediction_payload(
        _result(damage_breakdown={
            "defender_current_hp": 300,
            "defender_max_hp": 300,
            "stat_sources": {"attack": "total", "defense": "total"},
            "runtime_sources": {},
            "special_damage_rule": None,
        }),
        {"battle_uid": "b1", "types": [7], "current_hp": 300, "max_hp": 300},
        DamageCalibration(multiplier=1.1, key="7120090"),
        SpecialDamageRule(),
    )

    assert payload["prediction"]["audit_key"] == "7120090:b1"
    assert payload["prediction"]["secondary_total"] == 0
    assert payload["prediction"]["confidence"] == "high"
    assert payload["prediction"]["accuracy_flags"] == ["calibrated"]
    assert payload["validation_hint"] is None
