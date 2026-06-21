"""伤害预测配置 store 测试。"""
from __future__ import annotations

import json

from src.analysis.damage.prediction_config import (
    DamageCalibrationStore,
    ServerPowerRuleStore,
    SpecialDamageRuleStore,
)
from src.analysis.damage_prediction import DamageCalibrationStore as LegacyDamageCalibrationStore


def test_calibration_store_reads_damage_calibration(tmp_path):
    path = tmp_path / "damage_calibration.json"
    path.write_text(json.dumps({
        "version": 1,
        "skills": {
            "900001": {
                "multiplier": 1.25,
                "sample_count": 4,
                "mae": 2.0,
                "mape": 0.2,
                "source_sessions": ["s1"],
                "notes": "unit",
            }
        },
    }), encoding="utf-8")

    calibration = DamageCalibrationStore(path).get(900001)

    assert calibration.is_present is True
    assert calibration.multiplier == 1.25
    assert calibration.sample_count == 4
    assert calibration.source_sessions == ("s1",)
    assert calibration.to_dict()["applied"] is True


def test_special_rule_store_reads_rule_and_sessions(tmp_path):
    path = tmp_path / "special_damage_rules.json"
    path.write_text(json.dumps({
        "version": 1,
        "skills": {
            "7060130": {
                "mode": "special_fixed_light_multihit",
                "element": 17,
                "hit_count": 4,
                "per_hit": 12,
                "source_sessions": ["battle"],
                "notes": "unit",
            }
        },
    }), encoding="utf-8")

    rule = SpecialDamageRuleStore(path).get(7060130)

    assert rule.is_present is True
    assert rule.to_dict()["applied"] is True
    assert rule.source_sessions == ("battle",)


def test_server_power_rule_store_returns_skills_dict(tmp_path):
    path = tmp_path / "server_power_rules.json"
    path.write_text(json.dumps({
        "version": 1,
        "skills": {
            "7020470": {"enabled": True, "mode": "multiplier_over_base_power"}
        },
    }), encoding="utf-8")

    rules = ServerPowerRuleStore(path).rules()

    assert rules["7020470"]["enabled"] is True


def test_prediction_module_reexports_legacy_store_class():
    assert LegacyDamageCalibrationStore is DamageCalibrationStore


def test_config_store_tolerates_missing_or_invalid_files(tmp_path):
    missing = DamageCalibrationStore(tmp_path / "missing.json").get(1)
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{not-json", encoding="utf-8")
    invalid = SpecialDamageRuleStore(invalid_path).get(1)

    assert missing.is_present is False
    assert invalid.is_present is False
