"""伤害预测解释 payload 和审计 key 测试。"""
from __future__ import annotations

from src.analysis.damage.prediction_config import DamageCalibration, SpecialDamageRule
from src.analysis.damage.prediction_explain import audit_key, explain_prediction
from src.analysis.damage.result import DamageResult


def _result(**overrides) -> DamageResult:
    data = {
        "skill_id": 900001,
        "skill_name": "测试伤害",
        "power": 80,
        "effective_power": 120,
        "damage_type": 2,
        "skill_element": 1,
        "skill_element_name": "火",
        "effectiveness": 2.0,
        "effectiveness_label": "克制",
        "is_stab": True,
        "expected_damage": 40,
        "pct_hp": 0.2,
        "can_ko": False,
        "energy_cost": 2,
        "confidence": "high",
        "hit_count": 2,
        "power_mult": 1.25,
        "weather_mult": 1.1,
        "damage_breakdown": {
            "defender_current_hp": 300,
            "defender_max_hp": 300,
            "stat_sources": {"attack": "total", "defense": "wiki"},
            "runtime_sources": {"has_damage_params": True},
            "server_power_rule": {"applied": True},
            "ability_level": 2,
            "damage_reduction": 0.8,
        },
        "warnings": [],
    }
    data.update(overrides)
    return DamageResult(**data)


def test_explain_prediction_preserves_formula_sources_and_multipliers():
    explain = explain_prediction(
        _result(),
        DamageCalibration(multiplier=1.2, key="900001"),
        SpecialDamageRule(mode="fixed", per_hit=10, hit_count=3, key="900001"),
    )

    assert explain["formula"].startswith("int((ATK / DEF)")
    assert explain["stat_sources"] == {"attack": "total", "defense": "wiki"}
    assert explain["multipliers"] == {
        "effectiveness": 2.0,
        "stab": 1.5,
        "weather": 1.1,
        "power": 1.25,
        "hit_count": 2,
    }
    assert explain["hooks"] == {
        "ability_level": 2,
        "damage_reduction": 0.8,
        "combo": True,
    }
    assert explain["calibration"]["multiplier"] == 1.2
    assert explain["special_damage_rule"]["mode"] == "fixed"
    assert explain["runtime_sources"] == {"has_damage_params": True}
    assert explain["server_power_rule"] == {"applied": True}


def test_explain_prediction_prefers_result_special_rule_marker():
    dr = _result(damage_breakdown={
        "defender_current_hp": 300,
        "defender_max_hp": 300,
        "special_damage_rule": {"mode": "runtime_marker"},
    })

    explain = explain_prediction(dr, DamageCalibration(), SpecialDamageRule(mode="config_rule"))

    assert explain["special_damage_rule"] == {"mode": "runtime_marker"}


def test_audit_key_prefers_stable_target_identity():
    dr = _result()

    assert audit_key(dr, {"battle_uid": "b1", "pet_id": 2}) == "900001:b1"
    assert audit_key(dr, {"pet_id": 2, "slot": 3}) == "900001:2"
    assert audit_key(dr, {"slot": 3, "name": "敌方"}) == "900001:3"
    assert audit_key(dr, {"name": "敌方"}) == "900001:敌方"
    assert audit_key(dr, {}) == "900001:?"
