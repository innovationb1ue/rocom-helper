"""机制审计统计口径。"""
from __future__ import annotations

from statistics import mean
from typing import Any, Dict, List, Tuple

from src.analysis.damage.audit_utils import has_value, optional_int


def mechanism_strategy_summary(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Tuple[int, float]]] = {}
    for sample in samples:
        actual = optional_int(sample.get("actual_total"))
        if actual is None:
            continue
        for name, total in (sample.get("strategy_totals") or {}).items():
            candidate = optional_int(total)
            if candidate is None:
                continue
            error = abs(candidate - actual)
            grouped.setdefault(name, []).append((error, error / max(1, actual)))
    return {
        name: {
            "samples": len(values),
            "mae": round(mean(error for error, _ in values), 2) if values else None,
            "mape": round(mean(pct for _, pct in values), 4) if values else None,
        }
        for name, values in sorted(grouped.items())
    }


def decomposition_summary(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    checked = [sample for sample in samples if sample.get("decomposition_matches") is not None]
    deltas = [
        abs(int(sample["decomposition_delta"]))
        for sample in checked
        if sample.get("decomposition_delta") is not None
    ]
    return {
        "checked": len(checked),
        "matched": sum(1 for sample in checked if sample.get("decomposition_matches") is True),
        "match_rate": round(
            sum(1 for sample in checked if sample.get("decomposition_matches") is True) / len(checked),
            4,
        ) if checked else None,
        "mae_delta": round(mean(deltas), 2) if deltas else None,
    }


def field_presence(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    fields = (
        "raw_damage", "rule_damage_param", "effect_damage_param",
        "buff_damage_param", "ex_damage_param", "damage_param_result",
        "matched_damage_param", "restraint_type", "damage_type", "cost_energy",
        "set_cost_info", "skill_buff", "enhance_info", "cr_damage_params",
        "extra_damage_type",
    )
    total = len(samples)
    return {
        field: {
            "count": sum(1 for sample in samples if has_value(sample.get(field))),
            "rate": round(
                sum(1 for sample in samples if has_value(sample.get(field))) / total,
                4,
            ) if total else None,
        }
        for field in fields
    }
