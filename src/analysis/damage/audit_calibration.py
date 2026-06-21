"""伤害审计报告到只读配置草案的转换。"""
from __future__ import annotations

from statistics import mean
from typing import Any, Dict, List


def build_damage_calibration(
    report: Dict[str, Any],
    *,
    min_samples: int = 3,
) -> Dict[str, Any]:
    """从审计报告生成只读校准配置草案。"""
    grouped = _group_calibration_samples(report)
    skills: Dict[str, Dict[str, Any]] = {}
    skipped: Dict[str, str] = {}
    for skill_id, samples in grouped.items():
        if len(samples) < min_samples:
            skipped[skill_id] = "sample_count_below_min"
            continue
        proposal = _calibration_for_skill(samples)
        if proposal is None:
            skipped[skill_id] = "missing_predicted_total"
            continue
        if proposal["after_mape"] >= proposal["before_mape"]:
            skipped[skill_id] = "mape_not_improved"
            continue
        skills[skill_id] = proposal["config"]

    return {
        "version": 1,
        "skills": dict(sorted(skills.items())),
        "meta": {
            "min_samples": min_samples,
            "source": "scripts.audit_damage_predictions",
            "skipped": skipped,
        },
    }


def build_special_damage_rules(report: Dict[str, Any]) -> Dict[str, Any]:
    """从协议账本生成特殊固定伤害规则草案。"""
    return {
        "version": 1,
        "skills": {},
        "meta": {
            "source": "scripts.audit_damage_predictions",
            "special_skill_ids": [],
            "excluded_skill_ids": [7060130],
            "excluded_reasons": {
                "7060130": "confirmed light special damage; reflect child effects settle after base damage"
            },
        },
    }


def _group_calibration_samples(report: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for sample in report.get("samples", []) or []:
        skill_id = sample.get("skill_id")
        predicted = sample.get("predicted_total")
        actual = sample.get("actual_total")
        if skill_id is None or predicted in (None, 0) or actual is None:
            continue
        grouped.setdefault(str(skill_id), []).append(sample)
    return grouped


def _calibration_for_skill(samples: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    before_errors = [
        abs(int(sample["predicted_total"]) - int(sample["actual_total"])) / max(1, int(sample["actual_total"]))
        for sample in samples
    ]
    pred_sum = sum(int(sample["predicted_total"]) for sample in samples)
    actual_sum = sum(int(sample["actual_total"]) for sample in samples)
    if pred_sum <= 0:
        return None
    multiplier = actual_sum / pred_sum
    adjusted = [max(1, round(int(sample["predicted_total"]) * multiplier)) for sample in samples]
    abs_errors = [
        abs(adj - int(sample["actual_total"]))
        for adj, sample in zip(adjusted, samples)
    ]
    after_errors = [
        err / max(1, int(sample["actual_total"]))
        for err, sample in zip(abs_errors, samples)
    ]
    before_mape = mean(before_errors) if before_errors else 0.0
    after_mape = mean(after_errors) if after_errors else 0.0
    sessions = sorted({str(sample.get("session")) for sample in samples if sample.get("session")})
    return {
        "before_mape": before_mape,
        "after_mape": after_mape,
        "config": {
            "multiplier": round(multiplier, 6),
            "sample_count": len(samples),
            "mae": round(mean(abs_errors), 2) if abs_errors else None,
            "mape": round(after_mape, 4),
            "source_sessions": sessions,
            "notes": f"auto suggested from damage ledger; baseline_mape={round(before_mape, 4)}",
        },
    }
