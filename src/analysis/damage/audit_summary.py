"""普通伤害审计样本的汇总统计。"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Dict, List


def summarize_damage_samples(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总单场直接技能伤害审计样本。"""
    matched = [sample for sample in samples if sample.get("predicted_total") is not None]
    abs_errors = [sample["abs_error"] for sample in matched if sample.get("abs_error") is not None]
    pct_errors = [sample["pct_error"] for sample in matched if sample.get("pct_error") is not None]
    high_conf = [sample for sample in matched if sample.get("confidence") == "high"]
    return {
        "total_direct_damage": len(samples),
        "matched_predictions": len(matched),
        "mae": round(mean(abs_errors), 2) if abs_errors else None,
        "mape": round(mean(pct_errors), 4) if pct_errors else None,
        "within_10pct": sum(
            1 for sample in matched
            if sample.get("pct_error") is not None and sample["pct_error"] <= 0.10
        ),
        "within_25pct": sum(
            1 for sample in matched
            if sample.get("pct_error") is not None and sample["pct_error"] <= 0.25
        ),
        "high_confidence_samples": len(high_conf),
        "source_counts": source_counts(matched),
        "candidate_strategies": candidate_strategy_summary(matched),
        "catastrophic_high_confidence": [
            sample for sample in high_conf
            if sample.get("pct_error") is not None and sample["pct_error"] > 0.5
        ],
        "samples": samples,
    }


def summarize_multi_session_damage_audit(reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate several damage-audit reports without losing per-session detail."""
    all_samples: List[Dict[str, Any]] = []
    for session, report in reports.items():
        for sample in report.get("samples", []):
            all_samples.append({"session": session, **sample})

    matched = [sample for sample in all_samples if sample.get("predicted_total") is not None]
    abs_errors = [sample["abs_error"] for sample in matched if sample.get("abs_error") is not None]
    pct_errors = [sample["pct_error"] for sample in matched if sample.get("pct_error") is not None]

    return {
        "sessions": list(reports.keys()),
        "session_count": len(reports),
        "total_direct_damage": len(all_samples),
        "matched_predictions": len(matched),
        "mae": round(mean(abs_errors), 2) if abs_errors else None,
        "mape": round(mean(pct_errors), 4) if pct_errors else None,
        "within_10pct": sum(
            1 for sample in matched
            if sample.get("pct_error") is not None and sample["pct_error"] <= 0.10
        ),
        "within_25pct": sum(
            1 for sample in matched
            if sample.get("pct_error") is not None and sample["pct_error"] <= 0.25
        ),
        "source_counts": source_counts(matched),
        "candidate_strategies": candidate_strategy_summary(matched),
        "by_skill": group_samples(all_samples, "skill_name"),
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
            sample for sample in all_samples
            if sample.get("predicted_total") is None
        ][:20],
        "catastrophic_high_confidence": [
            sample for sample in matched
            if sample.get("confidence") == "high"
            and sample.get("pct_error") is not None
            and sample["pct_error"] > 0.5
        ],
        "samples": all_samples,
    }


def source_counts(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    return {
        "power_source": dict(Counter(str(sample.get("power_source") or "") for sample in samples)),
        "energy_cost_source": dict(Counter(str(sample.get("energy_cost_source") or "") for sample in samples)),
        "effectiveness_source": dict(Counter(str(sample.get("effectiveness_source") or "") for sample in samples)),
        "server_power_applied": dict(Counter(str(bool(sample.get("server_power_applied"))) for sample in samples)),
    }


def candidate_strategy_summary(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
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


def group_samples(samples: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for sample in samples:
        name = str(sample.get(key) or "?")
        grouped.setdefault(name, []).append(sample)

    out: Dict[str, Dict[str, Any]] = {}
    for name, items in grouped.items():
        matched = [sample for sample in items if sample.get("predicted_total") is not None]
        abs_errors = [sample["abs_error"] for sample in matched if sample.get("abs_error") is not None]
        pct_errors = [sample["pct_error"] for sample in matched if sample.get("pct_error") is not None]
        out[name] = {
            "total": len(items),
            "matched": len(matched),
            "mae": round(mean(abs_errors), 2) if abs_errors else None,
            "mape": round(mean(pct_errors), 4) if pct_errors else None,
            "within_25pct": sum(
                1 for sample in matched
                if sample.get("pct_error") is not None and sample["pct_error"] <= 0.25
            ),
            "sessions": sorted({str(sample.get("session")) for sample in items if sample.get("session")}),
        }
    return dict(sorted(out.items(), key=lambda item: item[1]["total"], reverse=True))
