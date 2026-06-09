"""伤害预测服务的输出变换和解释构造。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.damage.prediction_config import DamageCalibration, SpecialDamageRule
from src.analysis.damage import (
    prediction_adjustments,
    prediction_explain,
    prediction_payload,
    prediction_quality,
    prediction_secondary,
)
from src.analysis.damage.result import DamageResult


def apply_special_rule(dr: DamageResult, rule: SpecialDamageRule) -> DamageResult:
    return prediction_adjustments.apply_special_rule(dr, rule)


def apply_calibration(dr: DamageResult, calibration: DamageCalibration) -> DamageResult:
    return prediction_adjustments.apply_calibration(dr, calibration)


def accuracy_flags(dr: DamageResult, calibration: DamageCalibration) -> List[str]:
    return prediction_quality.accuracy_flags(dr, calibration)


def prediction_confidence(base: str, flags: List[str]) -> str:
    return prediction_quality.prediction_confidence(base, flags)


def validation_hint(flags: List[str]) -> Optional[str]:
    return prediction_quality.validation_hint(flags)


def secondary_effects(dr: DamageResult, defender: Dict[str, Any]) -> List[Dict[str, Any]]:
    return prediction_secondary.secondary_effects(dr, defender)


def explain_prediction(
    dr: DamageResult,
    calibration: DamageCalibration,
    special_rule: SpecialDamageRule,
) -> Dict[str, Any]:
    return prediction_explain.explain_prediction(dr, calibration, special_rule)


def audit_key(dr: DamageResult, defender: Dict[str, Any]) -> str:
    return prediction_explain.audit_key(dr, defender)


def build_prediction_payload(
    adjusted: DamageResult,
    defender: Dict[str, Any],
    calibration: DamageCalibration,
    special_rule: SpecialDamageRule,
) -> Dict[str, Any]:
    return prediction_payload.build_prediction_payload(adjusted, defender, calibration, special_rule)
