"""回放伤害预测对账。

只统计带技能名的直接技能伤害；中毒、天气、回合末等无技能名伤害不进入准确率指标。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from collections import Counter
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
    power_source: Optional[str]
    energy_cost_source: Optional[str]
    effectiveness_source: Optional[str]
    candidate_totals: Dict[str, int]
    candidate_abs_errors: Dict[str, int]
    ledger_ids: List[str]
    actual_source: str
    actual_confidence: str

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
        "source_counts": _source_counts([s.to_dict() for s in matched]),
        "candidate_strategies": _candidate_strategy_summary([s.to_dict() for s in matched]),
        "catastrophic_high_confidence": catastrophic_high,
        "samples": [s.to_dict() for s in samples],
    }


def build_multi_session_damage_audit(reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate several damage-audit reports without losing per-session detail."""
    all_samples: List[Dict[str, Any]] = []
    for session, report in reports.items():
        for sample in report.get("samples", []):
            all_samples.append({"session": session, **sample})

    matched = [s for s in all_samples if s.get("predicted_total") is not None]
    abs_errors = [s["abs_error"] for s in matched if s.get("abs_error") is not None]
    pct_errors = [s["pct_error"] for s in matched if s.get("pct_error") is not None]

    return {
        "sessions": list(reports.keys()),
        "session_count": len(reports),
        "total_direct_damage": len(all_samples),
        "matched_predictions": len(matched),
        "mae": round(mean(abs_errors), 2) if abs_errors else None,
        "mape": round(mean(pct_errors), 4) if pct_errors else None,
        "within_10pct": sum(1 for s in matched if s.get("pct_error") is not None and s["pct_error"] <= 0.10),
        "within_25pct": sum(1 for s in matched if s.get("pct_error") is not None and s["pct_error"] <= 0.25),
        "source_counts": _source_counts(matched),
        "candidate_strategies": _candidate_strategy_summary(matched),
        "by_skill": _group_samples(all_samples, "skill_name"),
        "by_session": {
            session: {
                "total_direct_damage": report.get("total_direct_damage", 0),
                "matched_predictions": report.get("matched_predictions", 0),
                "mae": report.get("mae"),
                "mape": report.get("mape"),
                "within_10pct": report.get("within_10pct", 0),
                "within_25pct": report.get("within_25pct", 0),
            }
            for session, report in reports.items()
        },
        "missing_prediction_samples": [
            s for s in all_samples
            if s.get("predicted_total") is None
        ][:20],
        "catastrophic_high_confidence": [
            s for s in matched
            if s.get("confidence") == "high"
            and s.get("pct_error") is not None
            and s["pct_error"] > 0.5
        ],
        "samples": all_samples,
    }


def build_damage_calibration(
    report: Dict[str, Any],
    *,
    min_samples: int = 3,
) -> Dict[str, Any]:
    """从审计报告生成只读校准配置草案。"""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for sample in report.get("samples", []) or []:
        skill_id = sample.get("skill_id")
        predicted = sample.get("predicted_total")
        actual = sample.get("actual_total")
        if skill_id is None or predicted in (None, 0) or actual is None:
            continue
        grouped.setdefault(str(skill_id), []).append(sample)

    skills: Dict[str, Dict[str, Any]] = {}
    skipped: Dict[str, str] = {}
    for skill_id, samples in grouped.items():
        if len(samples) < min_samples:
            skipped[skill_id] = "sample_count_below_min"
            continue
        before_errors = [
            abs(int(s["predicted_total"]) - int(s["actual_total"])) / max(1, int(s["actual_total"]))
            for s in samples
        ]
        pred_sum = sum(int(s["predicted_total"]) for s in samples)
        actual_sum = sum(int(s["actual_total"]) for s in samples)
        if pred_sum <= 0:
            skipped[skill_id] = "missing_predicted_total"
            continue
        multiplier = actual_sum / pred_sum
        adjusted = [max(1, round(int(s["predicted_total"]) * multiplier)) for s in samples]
        abs_errors = [
            abs(adj - int(sample["actual_total"]))
            for adj, sample in zip(adjusted, samples)
        ]
        after_errors = [
            err / max(1, int(sample["actual_total"]))
            for err, sample in zip(abs_errors, samples)
        ]
        before_mape = mean(before_errors) if before_errors else None
        after_mape = mean(after_errors) if after_errors else None
        if before_mape is not None and after_mape is not None and after_mape >= before_mape:
            skipped[skill_id] = "mape_not_improved"
            continue
        sessions = sorted({str(s.get("session")) for s in samples if s.get("session")})
        skills[skill_id] = {
            "multiplier": round(multiplier, 6),
            "sample_count": len(samples),
            "mae": round(mean(abs_errors), 2) if abs_errors else None,
            "mape": round(after_mape, 4) if after_mape is not None else None,
            "source_sessions": sessions,
            "notes": (
                "auto suggested from damage ledger; "
                f"baseline_mape={round(before_mape, 4) if before_mape is not None else None}"
            ),
        }

    return {
        "version": 1,
        "skills": dict(sorted(skills.items())),
        "meta": {
            "min_samples": min_samples,
            "source": "scripts.audit_damage_predictions",
            "skipped": skipped,
        },
    }


def _source_counts(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    return {
        "power_source": dict(Counter(str(s.get("power_source") or "") for s in samples)),
        "energy_cost_source": dict(Counter(str(s.get("energy_cost_source") or "") for s in samples)),
        "effectiveness_source": dict(Counter(str(s.get("effectiveness_source") or "") for s in samples)),
    }


def _candidate_strategy_summary(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[int]] = {}
    grouped_pct: Dict[str, List[float]] = {}
    for sample in samples:
        actual = int(sample.get("actual_total") or 0)
        for name, abs_error in (sample.get("candidate_abs_errors") or {}).items():
            grouped.setdefault(name, []).append(abs_error)
            grouped_pct.setdefault(name, []).append(abs_error / max(1, actual))
    return {
        name: {
            "samples": len(errors),
            "mae": round(mean(errors), 2) if errors else None,
            "mape": round(mean(grouped_pct.get(name, [])), 4) if grouped_pct.get(name) else None,
        }
        for name, errors in sorted(grouped.items())
    }


def _group_samples(samples: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for sample in samples:
        name = str(sample.get(key) or "?")
        grouped.setdefault(name, []).append(sample)

    out: Dict[str, Dict[str, Any]] = {}
    for name, items in grouped.items():
        matched = [s for s in items if s.get("predicted_total") is not None]
        abs_errors = [s["abs_error"] for s in matched if s.get("abs_error") is not None]
        pct_errors = [s["pct_error"] for s in matched if s.get("pct_error") is not None]
        out[name] = {
            "total": len(items),
            "matched": len(matched),
            "mae": round(mean(abs_errors), 2) if abs_errors else None,
            "mape": round(mean(pct_errors), 4) if pct_errors else None,
            "within_25pct": sum(1 for s in matched if s.get("pct_error") is not None and s["pct_error"] <= 0.25),
            "sessions": sorted({str(s.get("session")) for s in items if s.get("session")}),
        }
    return dict(sorted(out.items(), key=lambda item: item[1]["total"], reverse=True))


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
            ledger_records = _ledger_records_for_damage(event.state_after, detail)
            if ledger_records:
                ledger_total = sum(_ledger_actual_damage(item) for item in ledger_records)
                hit_count = max(hit_count, len(ledger_records))
                actual_total = ledger_total
                actual_per_hit = int(round(ledger_total / max(1, hit_count)))
                actual_source = "+".join(sorted({str(item.get("source")) for item in ledger_records if item.get("source")})) or "damage_ledger"
                confidences = {str(item.get("confidence") or "") for item in ledger_records}
                actual_confidence = "low" if "low" in confidences else ("medium" if "medium" in confidences else "high")
                ledger_ids = [str(item.get("ledger_id")) for item in ledger_records if item.get("ledger_id")]
            else:
                actual_per_hit = int(detail.get("actual_damage") or detail.get("damage") or 0)
                actual_total = actual_per_hit * hit_count
                actual_source = "formatted_event"
                actual_confidence = "medium"
                ledger_ids = []
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
                breakdown = prediction.get("damage_breakdown") or {}
            else:
                breakdown = {}

            error = predicted_total - actual_total if predicted_total is not None else None
            abs_error = abs(error) if error is not None else None
            pct_error = abs_error / max(1, actual_total) if abs_error is not None else None
            candidates = _candidate_totals(predicted_total, prediction or {}, breakdown)
            candidate_errors = {
                name: abs(total - actual_total)
                for name, total in candidates.items()
            }
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
                power_source=breakdown.get("power_source"),
                energy_cost_source=breakdown.get("energy_cost_source"),
                effectiveness_source=breakdown.get("effectiveness_source"),
                candidate_totals=candidates,
                candidate_abs_errors=candidate_errors,
                ledger_ids=ledger_ids,
                actual_source=actual_source,
                actual_confidence=actual_confidence,
            )


def _ledger_records_for_damage(state: Dict[str, Any], detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    ledger = ((state.get("field_context") or {}).get("damage_ledger") or [])
    by_id = {
        str(item.get("ledger_id")): item
        for item in ledger
        if item.get("ledger_id")
    }
    wanted = [str(item) for item in detail.get("ledger_ids") or []]
    if detail.get("ledger_id") is not None:
        wanted.append(str(detail["ledger_id"]))
    records = [by_id[item] for item in wanted if item in by_id]
    if records:
        return records
    skill_name = detail.get("skill_name")
    hp_after = detail.get("hp_after")
    candidates = [
        item for item in ledger
        if item.get("event_kind") == "damage"
        and item.get("skill_name") == skill_name
        and (hp_after is None or item.get("hp_after") == hp_after)
    ]
    return candidates[-1:] if candidates else []


def _ledger_actual_damage(item: Dict[str, Any]) -> int:
    before = item.get("hp_before")
    after = item.get("hp_after")
    if before is not None and after is not None:
        return max(0, int(before) - int(after))
    if item.get("actual_damage") is not None:
        return max(0, int(item["actual_damage"]))
    if item.get("damage") is not None:
        return max(0, int(item["damage"]))
    return 0


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


def _candidate_totals(
    predicted_total: Optional[int],
    prediction: Dict[str, Any],
    breakdown: Dict[str, Any],
) -> Dict[str, int]:
    if predicted_total is None:
        return {}
    out = {"production": int(predicted_total)}
    power = breakdown.get("final_power") or prediction.get("power")
    base_power = breakdown.get("base_power")
    if power and base_power and power != base_power:
        out["static_power_fallback"] = max(1, round(predicted_total * base_power / power))
    server_runtime = breakdown.get("server_runtime") or {}
    calc_eff = server_runtime.get("calc_effectiveness")
    display_eff = server_runtime.get("display_effectiveness")
    runtime_power = breakdown.get("runtime_power")
    if server_runtime.get("power_source") == "server_damage_params" and runtime_power and base_power:
        out["server_target_power_keep_restraint"] = max(1, round(predicted_total * runtime_power / base_power))
        if calc_eff and display_eff:
            out["server_target_power_no_restraint"] = max(
                1,
                round(out["server_target_power_keep_restraint"] / max(float(display_eff), 0.001)),
            )
    return out
