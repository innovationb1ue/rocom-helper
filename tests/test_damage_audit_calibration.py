"""伤害审计校准草案测试。"""
from __future__ import annotations

from src.analysis.damage.audit_calibration import (
    build_damage_calibration,
    build_special_damage_rules,
)
from src.analysis.damage_audit import build_damage_calibration as legacy_build_damage_calibration


def _sample(skill_id=1, predicted=100, actual=200, session="s1"):
    return {
        "skill_id": skill_id,
        "predicted_total": predicted,
        "actual_total": actual,
        "session": session,
    }


def test_build_damage_calibration_suggests_improving_multiplier():
    report = {"samples": [_sample(), _sample(), _sample(session="s2")]}

    calibration = build_damage_calibration(report, min_samples=3)

    assert calibration["skills"]["1"]["multiplier"] == 2.0
    assert calibration["skills"]["1"]["sample_count"] == 3
    assert calibration["skills"]["1"]["source_sessions"] == ["s1", "s2"]
    assert calibration["meta"]["skipped"] == {}


def test_build_damage_calibration_skips_low_sample_count_and_non_improvements():
    low_count = {"samples": [_sample(skill_id=1)]}
    already_good = {
        "samples": [
            _sample(skill_id=2, predicted=100, actual=100),
            _sample(skill_id=2, predicted=100, actual=100),
            _sample(skill_id=2, predicted=100, actual=100),
        ]
    }

    assert build_damage_calibration(low_count, min_samples=3)["meta"]["skipped"]["1"] == "sample_count_below_min"
    assert build_damage_calibration(already_good, min_samples=3)["meta"]["skipped"]["2"] == "mape_not_improved"


def test_build_special_damage_rules_keeps_reflect_exclusion_contract():
    rules = build_special_damage_rules({"samples": []})

    assert rules["skills"] == {}
    assert 7060130 in rules["meta"]["excluded_skill_ids"]
    assert "confirmed light special damage" in rules["meta"]["excluded_reasons"]["7060130"]


def test_damage_audit_module_reexports_calibration_builder_behavior():
    report = {"samples": [_sample(), _sample(), _sample()]}

    assert legacy_build_damage_calibration(report)["skills"]["1"]["multiplier"] == 2.0
