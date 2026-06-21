"""技能运行时伤害参数机制审计汇总。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.analysis.damage import audit_mechanism_recommendation
from src.analysis.damage import audit_mechanism_stats
from src.analysis.damage.audit_utils import optional_int, restraint_to_multiplier


def build_mechanism_report(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从机制样本生成单场机制审计报告。"""
    by_skill = mechanism_group_by_skill(samples)
    strategy_compare = mechanism_strategy_summary(samples)
    return {
        "total_samples": len(samples),
        "matched_runtime_samples": sum(1 for sample in samples if sample.get("matched_damage_param") is not None),
        "samples": samples,
        "by_skill": by_skill,
        "strategy_compare": strategy_compare,
        "damage_param_strategy_compare": strategy_compare,
        "decomposition_checks": {
            "overall": decomposition_summary(samples),
            "by_skill": {
                name: item.get("decomposition_checks", {})
                for name, item in by_skill.items()
            },
        },
        "field_presence": {
            "overall": field_presence(samples),
            "by_skill": {
                name: item.get("field_presence", {})
                for name, item in by_skill.items()
            },
        },
        "recommendations": {
            name: item.get("recommendation", {})
            for name, item in by_skill.items()
        },
    }


def build_multi_session_mechanism_report(reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """聚合多场机制审计报告。"""
    samples: List[Dict[str, Any]] = []
    for session, report in reports.items():
        for sample in report.get("samples", []) or []:
            item = dict(sample)
            item.setdefault("session", session)
            samples.append(item)
    report = build_mechanism_report(samples)
    return {
        "sessions": list(reports.keys()),
        "session_count": len(reports),
        **report,
    }


def candidate_totals(
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


def mechanism_strategy_totals(
    predicted_total: Optional[int],
    prediction: Dict[str, Any],
    breakdown: Dict[str, Any],
    matched_damage_param: Any,
    restraint_type: Any,
) -> Dict[str, int]:
    out = candidate_totals(predicted_total, prediction, breakdown)
    if predicted_total is None:
        return out
    final_power = optional_int(breakdown.get("final_power") or breakdown.get("effective_power"))
    matched = optional_int(matched_damage_param)
    if not final_power or not matched:
        return out
    out["damage_param_as_effective_power"] = max(1, round(int(predicted_total) * matched / final_power))
    restraint_mult = restraint_to_multiplier(restraint_type)
    if restraint_mult:
        neutralized = matched / max(restraint_mult, 0.001)
        out["damage_param_neutralized_by_restraint"] = max(
            1,
            round(int(predicted_total) * neutralized / final_power),
        )
    return out


def decomposition_check(
    runtime_skill: Dict[str, Any],
    matched_damage_param: Any,
) -> Tuple[Optional[int], Optional[int], Optional[bool]]:
    matched = optional_int(matched_damage_param)
    if matched is None:
        return None, None, None
    fields = (
        "raw_damage", "rule_damage_param", "effect_damage_param",
        "buff_damage_param", "ex_damage_param",
    )
    parts = [optional_int(runtime_skill.get(field)) for field in fields]
    if all(part is None for part in parts):
        return None, None, None
    total = sum(part or 0 for part in parts)
    delta = total - matched
    return total, delta, abs(delta) <= 1


def mechanism_group_by_skill(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for sample in samples:
        grouped.setdefault(str(sample.get("skill_name") or "?"), []).append(sample)
    out: Dict[str, Dict[str, Any]] = {}
    for name, items in grouped.items():
        out[name] = {
            "total": len(items),
            "sessions": sorted({str(sample.get("session")) for sample in items if sample.get("session")}),
            "strategy_compare": mechanism_strategy_summary(items),
            "decomposition_checks": decomposition_summary(items),
            "field_presence": field_presence(items),
        }
        out[name]["recommendation"] = mechanism_recommendation(items, out[name])
    return dict(sorted(out.items(), key=lambda item: item[1]["total"], reverse=True))


def mechanism_strategy_summary(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return audit_mechanism_stats.mechanism_strategy_summary(samples)


def decomposition_summary(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    return audit_mechanism_stats.decomposition_summary(samples)


def field_presence(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    return audit_mechanism_stats.field_presence(samples)


def mechanism_recommendation(
    samples: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    return audit_mechanism_recommendation.mechanism_recommendation(samples, summary)
