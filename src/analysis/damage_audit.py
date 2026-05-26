"""回放伤害预测对账。

只统计带技能名的直接技能伤害；中毒、天气、回合末等无技能名伤害不进入准确率指标。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

from src.analysis.replay_runner import ReplayResult


@dataclass
class DamageAuditSample:
    round_num: int
    event_index: int
    skill_name: str
    skill_id: Optional[int]
    target_side: str
    actual_per_hit: int
    actual_total: int
    predicted_per_hit: Optional[int]
    predicted_total: Optional[int]
    hit_count: int
    error: Optional[int]
    abs_error: Optional[int]
    pct_error: Optional[float]
    confidence: Optional[str]
    accuracy_flags: List[str]
    validation_hint: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_damage_audit(result: ReplayResult) -> Dict[str, Any]:
    samples = list(iter_damage_audit_samples(result))
    matched = [s for s in samples if s.predicted_total is not None]
    abs_errors = [s.abs_error for s in matched if s.abs_error is not None]
    pct_errors = [s.pct_error for s in matched if s.pct_error is not None]
    high_conf = [s for s in matched if s.confidence == "high"]
    catastrophic_high = [
        s.to_dict()
        for s in high_conf
        if s.pct_error is not None and s.pct_error > 0.5
    ]
    return {
        "total_direct_damage": len(samples),
        "matched_predictions": len(matched),
        "mae": round(mean(abs_errors), 2) if abs_errors else None,
        "mape": round(mean(pct_errors), 4) if pct_errors else None,
        "within_10pct": sum(1 for s in matched if s.pct_error is not None and s.pct_error <= 0.10),
        "within_25pct": sum(1 for s in matched if s.pct_error is not None and s.pct_error <= 0.25),
        "high_confidence_samples": len(high_conf),
        "catastrophic_high_confidence": catastrophic_high,
        "samples": [s.to_dict() for s in samples],
    }


def iter_damage_audit_samples(result: ReplayResult) -> Iterable[DamageAuditSample]:
    latest_advice: Optional[Dict[str, Any]] = None
    for event in result.events:
        advice = event.battle_advice or latest_advice
        if event.battle_advice:
            latest_advice = event.battle_advice

        for formatted in event.formatted_events:
            if formatted.get("kind") != "damage":
                continue
            detail = formatted.get("detail", {})
            skill_name = detail.get("skill_name")
            if not skill_name:
                continue

            hit_count = int(detail.get("hit_count") or 1)
            actual_per_hit = int(detail.get("damage") or 0)
            actual_total = actual_per_hit * hit_count
            target_side = str(detail.get("target_side") or "")
            prediction = _find_prediction(advice, skill_name, target_side)
            predicted_total = None
            predicted_per_hit = None
            skill_id = None
            confidence = None
            flags: List[str] = []
            hint = None
            if prediction:
                skill_id = prediction.get("skill_id")
                pred_obj = prediction.get("prediction") or {}
                predicted_total = pred_obj.get("total")
                predicted_per_hit = pred_obj.get("per_hit")
                if predicted_total is None:
                    predicted_total = prediction.get("total_max_damage") or prediction.get("expected_damage")
                if predicted_per_hit is None:
                    predicted_per_hit = prediction.get("expected_damage")
                confidence = pred_obj.get("confidence") or prediction.get("confidence")
                flags = list(pred_obj.get("accuracy_flags") or [])
                hint = prediction.get("validation_hint")

            error = predicted_total - actual_total if predicted_total is not None else None
            abs_error = abs(error) if error is not None else None
            pct_error = abs_error / max(1, actual_total) if abs_error is not None else None
            yield DamageAuditSample(
                round_num=event.round_num,
                event_index=event.index,
                skill_name=str(skill_name),
                skill_id=skill_id,
                target_side=target_side,
                actual_per_hit=actual_per_hit,
                actual_total=actual_total,
                predicted_per_hit=predicted_per_hit,
                predicted_total=predicted_total,
                hit_count=hit_count,
                error=error,
                abs_error=abs_error,
                pct_error=round(pct_error, 4) if pct_error is not None else None,
                confidence=confidence,
                accuracy_flags=flags,
                validation_hint=hint,
            )


def _find_prediction(
    advice: Optional[Dict[str, Any]], skill_name: str, target_side: str,
) -> Optional[Dict[str, Any]]:
    if not advice:
        return None
    key = "skill_analysis" if target_side == "敌方" else "opp_skill_analysis"
    for pred in advice.get(key, []):
        if pred.get("skill_name") == skill_name:
            return pred
    return None
