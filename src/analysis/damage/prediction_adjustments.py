"""伤害预测结果调整规则。"""
from __future__ import annotations

from src.analysis.damage.prediction_config import DamageCalibration, SpecialDamageRule
from src.analysis.damage.result import DamageResult, damage_result_from_dict


def apply_special_rule(dr: DamageResult, rule: SpecialDamageRule) -> DamageResult:
    """按特殊固定伤害配置替换预测结果。"""
    special = dr.damage_breakdown.get("special_damage_rule")
    if special is None:
        return dr
    data = dr.to_dict()
    if rule.is_present and rule.per_hit is not None and rule.hit_count is not None:
        per_hit = int(rule.per_hit)
        hit_count = max(1, int(rule.hit_count))
        total = per_hit * hit_count
        defender_max_hp = dr.damage_breakdown.get("defender_max_hp") or 1
        defender_cur_hp = dr.damage_breakdown.get("defender_current_hp") or 0
        data["expected_damage"] = per_hit
        data["hit_count"] = hit_count
        data["pct_hp"] = round(total / max(1, defender_max_hp), 3)
        data["can_ko"] = total >= defender_cur_hp
    rule_payload = rule.to_dict() if rule.is_present else {}
    data["confidence"] = "low" if not rule.is_present else dr.confidence
    data["damage_breakdown"] = {
        **dr.damage_breakdown,
        "special_damage_rule": {
            **special,
            **rule_payload,
            "source": "config" if rule.is_present else special.get("source", "config_missing"),
        },
    }
    return damage_result_from_dict(data)


def apply_calibration(dr: DamageResult, calibration: DamageCalibration) -> DamageResult:
    """按回放校准倍率调整预测结果。"""
    if not calibration.is_present or calibration.multiplier == 1.0:
        return dr
    adjusted = int(max(1, round(dr.expected_damage * calibration.multiplier)))
    total = adjusted * dr.hit_count
    defender_max_hp = dr.damage_breakdown.get("defender_max_hp") or 1
    defender_cur_hp = dr.damage_breakdown.get("defender_current_hp") or 0
    data = dr.to_dict()
    data["expected_damage"] = adjusted
    data["pct_hp"] = round(total / max(1, defender_max_hp), 3)
    data["can_ko"] = total >= defender_cur_hp
    data["damage_breakdown"] = {
        **dr.damage_breakdown,
        "calibration_mult": calibration.multiplier,
        "raw_expected_damage": dr.expected_damage,
    }
    return damage_result_from_dict(data)
