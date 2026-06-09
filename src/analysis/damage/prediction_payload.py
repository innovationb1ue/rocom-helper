"""伤害预测顶层 payload 组装。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.damage.prediction_config import DamageCalibration, SpecialDamageRule
from src.analysis.damage import prediction_explain, prediction_quality, prediction_secondary
from src.analysis.damage.result import DamageResult


def build_prediction_payload(
    adjusted: DamageResult,
    defender: Dict[str, Any],
    calibration: DamageCalibration,
    special_rule: SpecialDamageRule,
) -> Dict[str, Any]:
    """组装 DamagePredictionService 对外返回的兼容 payload。"""
    flags = prediction_quality.accuracy_flags(adjusted, calibration)
    confidence = prediction_quality.prediction_confidence(adjusted.confidence, flags)
    hint = prediction_quality.validation_hint(flags)
    explain = prediction_explain.explain_prediction(adjusted, calibration, special_rule)
    target_hp_before = adjusted.damage_breakdown.get("defender_current_hp") or 0
    predicted_hp_after = max(0, int(target_hp_before) - adjusted.total_damage)
    secondary = prediction_secondary.secondary_effects(adjusted, defender)
    secondary_total = sum(int(item.get("damage") or 0) for item in secondary)
    tactical_total = adjusted.total_damage + secondary_total
    predicted_hp_after_with_secondary = max(0, int(target_hp_before) - tactical_total)
    runtime_sources = adjusted.damage_breakdown.get("runtime_sources") or {}

    return {
        "result": adjusted,
        "prediction": {
            "audit_key": prediction_explain.audit_key(adjusted, defender),
            "per_hit": adjusted.expected_damage,
            "total": adjusted.total_damage,
            "hit_count": adjusted.hit_count,
            "target_hp_before": target_hp_before,
            "predicted_hp_after": predicted_hp_after,
            "predicted_hp_after_with_secondary": predicted_hp_after_with_secondary,
            "secondary_total": secondary_total,
            "tactical_total": tactical_total,
            "secondary_effects": secondary,
            "runtime_sources": runtime_sources,
            "confidence": confidence,
            "accuracy_flags": flags,
        },
        "explain": {**explain, "secondary_effects": secondary},
        "validation_hint": hint,
    }
