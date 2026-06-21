"""机制审计推荐状态策略。"""
from __future__ import annotations

from typing import Any, Dict, List


_LIGHT_SPECIAL_SKILL_ID = 7060130
_DAMAGE_PARAM_STRATEGIES = {
    "damage_param_as_effective_power",
    "damage_param_neutralized_by_restraint",
}


def mechanism_recommendation(
    samples: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    """根据机制审计策略误差给出保守推荐状态。"""
    if len(samples) < 3:
        return {"status": "insufficient_samples", "reason": "matched direct damage samples below 3"}

    skill_ids = {sample.get("skill_id") for sample in samples if sample.get("skill_id") is not None}
    if _LIGHT_SPECIAL_SKILL_ID in skill_ids:
        return {
            "status": "audit_only",
            "reason": "confirmed light special damage; child effects settle after base damage",
        }

    strategies = summary.get("strategy_compare") or {}
    production = strategies.get("production") or {}
    production_mape = production.get("mape")
    damage_candidates = _comparable_damage_candidates(strategies)
    if not damage_candidates or production_mape is None:
        return {"status": "audit_only", "reason": "damage-param candidates are not comparable yet"}

    best_name, best = min(damage_candidates.items(), key=lambda item: item[1]["mape"])
    if best["mape"] <= production_mape * 0.85:
        status = (
            "likely_effective_param"
            if best_name == "damage_param_as_effective_power"
            else "candidate_for_whitelist"
        )
        return {
            "status": status,
            "reason": f"{best_name} improves MAPE from {production_mape} to {best['mape']}",
            "best_strategy": best_name,
        }

    return {
        "status": "audit_only",
        "reason": "damage-param candidates do not materially improve production",
    }


def _comparable_damage_candidates(strategies: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        name: item
        for name, item in strategies.items()
        if name in _DAMAGE_PARAM_STRATEGIES
        and item.get("samples", 0) >= 3
        and item.get("mape") is not None
    }
