from __future__ import annotations

import json

from src.analysis.damage_prediction import DamageCalibrationStore, DamagePredictionService


def _pet(name: str, atk: int = 200, defense: int = 150):
    return {
        "name": name,
        "types": [1],
        "current_hp": 300,
        "max_hp": 300,
        "energy": 10,
        "buffs": [],
        "stats": [
            {"name": "ATK", "total": atk},
            {"name": "DEF", "total": defense},
            {"name": "SPA", "total": atk},
            {"name": "SPD", "total": defense},
        ],
    }


def _skill(skill_id: int = 900001, power: int = 80):
    return {
        "id": skill_id,
        "name": "测试伤害",
        "dam_para": [power],
        "damage_type": 2,
        "skill_dam_type": 1,
        "energy_cost": [2],
        "desc": "造成物伤。",
    }


def test_prediction_contains_compatible_and_extended_fields(tmp_path):
    service = DamagePredictionService(calibration_store=DamageCalibrationStore(tmp_path / "missing.json"))
    pred = service.predict(_pet("我方"), _pet("敌方"), _skill())

    assert pred is not None
    assert pred["result"].expected_damage > 0
    assert pred["prediction"]["total"] == pred["result"].total_damage
    assert pred["prediction"]["audit_key"].startswith("900001:")
    assert pred["prediction"]["target_hp_before"] == 300
    assert pred["prediction"]["predicted_hp_after"] == max(0, 300 - pred["prediction"]["total"])
    assert isinstance(pred["prediction"]["runtime_sources"], dict)
    assert pred["prediction"]["confidence"] == "medium"
    assert "uncalibrated_skill" in pred["prediction"]["accuracy_flags"]
    assert pred["explain"]["stat_sources"]["attack"] == "total"
    assert pred["validation_hint"] == "技能尚未经过回放校准"


def test_prediction_marks_unmodeled_runtime_sources(tmp_path):
    service = DamagePredictionService(calibration_store=DamageCalibrationStore(tmp_path / "missing.json"))
    attacker = _pet("我方")
    attacker["skill_runtime"] = {
        "900001": {
            "set_cost_info": [{"type": 1}],
            "cr_damage_params": [{"rate": 2}],
        }
    }
    pred = service.predict(attacker, _pet("敌方"), _skill())

    assert pred is not None
    assert "runtime_effect_unmodeled" in pred["prediction"]["accuracy_flags"]
    assert pred["prediction"]["runtime_sources"]["has_set_cost_info"] is True


def test_calibration_multiplier_adjusts_damage(tmp_path):
    path = tmp_path / "damage_calibration.json"
    path.write_text(json.dumps({
        "version": 1,
        "skills": {
            "900001": {
                "multiplier": 2.0,
                "sample_count": 3,
                "mae": 1.0,
                "mape": 0.1,
                "source_sessions": ["unit"],
                "notes": "unit test",
            }
        },
    }), encoding="utf-8")
    service = DamagePredictionService(calibration_store=DamageCalibrationStore(path))
    raw = DamagePredictionService(calibration_store=DamageCalibrationStore(tmp_path / "missing.json")).predict(
        _pet("我方"), _pet("敌方"), _skill(),
    )
    calibrated = service.predict(_pet("我方"), _pet("敌方"), _skill())

    assert raw is not None and calibrated is not None
    assert calibrated["prediction"]["per_hit"] == raw["prediction"]["per_hit"] * 2
    assert calibrated["explain"]["calibration"]["applied"] is True
    assert "calibrated" in calibrated["prediction"]["accuracy_flags"]


def test_non_damage_skill_returns_none(tmp_path):
    service = DamagePredictionService(calibration_store=DamageCalibrationStore(tmp_path / "missing.json"))
    skill = {**_skill(), "damage_type": 1}

    assert service.predict(_pet("我方"), _pet("敌方"), skill) is None
