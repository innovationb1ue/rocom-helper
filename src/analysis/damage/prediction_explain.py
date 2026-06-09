"""伤害预测解释 payload 和审计 key 构造。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.damage.prediction_config import DamageCalibration, SpecialDamageRule
from src.analysis.damage.result import DamageResult


def explain_prediction(
    dr: DamageResult,
    calibration: DamageCalibration,
    special_rule: SpecialDamageRule,
) -> Dict[str, Any]:
    """构造预测解释信息，供 UI 展示和审计使用。"""
    breakdown = dr.damage_breakdown
    return {
        "formula": "int((ATK / DEF) * power * 0.9 * effectiveness * stab * weather * power_mult)",
        "stat_sources": breakdown.get("stat_sources", {}),
        "multipliers": {
            "effectiveness": dr.effectiveness,
            "stab": 1.5 if dr.is_stab else 1.0,
            "weather": dr.weather_mult,
            "power": dr.power_mult,
            "hit_count": dr.hit_count,
        },
        "hooks": {
            "ability_level": breakdown.get("ability_level"),
            "damage_reduction": breakdown.get("damage_reduction"),
            "combo": dr.hit_count > 1,
        },
        "calibration": calibration.to_dict(),
        "special_damage_rule": (
            dr.damage_breakdown.get("special_damage_rule")
            or special_rule.to_dict()
        ),
        "runtime_sources": breakdown.get("runtime_sources") or {},
        "server_power_rule": breakdown.get("server_power_rule") or {},
    }


def audit_key(dr: DamageResult, defender: Dict[str, Any]) -> str:
    """生成预测审计用的稳定 key。"""
    target = (
        defender.get("battle_uid")
        or defender.get("pet_id")
        or defender.get("slot")
        or defender.get("name")
        or "?"
    )
    return f"{dr.skill_id}:{target}"
