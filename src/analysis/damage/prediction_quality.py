"""伤害预测准确性标签、置信度和提示文案规则。"""
from __future__ import annotations

from typing import List, Optional

from src.analysis.damage.prediction_config import DamageCalibration
from src.analysis.damage.result import DamageResult


def accuracy_flags(dr: DamageResult, calibration: DamageCalibration) -> List[str]:
    """根据预测结果和配置状态生成准确性标签。"""
    flags: List[str] = []
    stat_sources = dr.damage_breakdown.get("stat_sources", {})
    runtime_sources = dr.damage_breakdown.get("runtime_sources") or {}
    if "wiki" in {stat_sources.get("attack"), stat_sources.get("defense")}:
        flags.append("estimated_stats")
    if calibration.is_present:
        flags.append("calibrated")
    else:
        flags.append("uncalibrated_skill")
    if dr.hit_count > 1:
        flags.append("multi_hit")
    if dr.damage_breakdown.get("special_damage_rule"):
        rule = dr.damage_breakdown["special_damage_rule"]
        flags.append("special_fixed_damage")
        if not rule.get("applied"):
            flags.append("special_damage_unmodeled")
    if any("能量不足" in warning for warning in dr.warnings):
        flags.append("energy_insufficient")
    if dr.confidence == "low":
        flags.append("low_stat_confidence")
    if runtime_sources.get("has_damage_params") and not runtime_sources.get("matched_target_key"):
        flags.append("runtime_target_unmatched")
    if any(
        runtime_sources.get(key)
        for key in ("has_set_cost_info", "has_cr_damage_params", "has_extra_damage_type", "has_skill_buff")
    ):
        flags.append("runtime_effect_unmodeled")
    return flags


def prediction_confidence(base: str, flags: List[str]) -> str:
    """把基础置信度和准确性标签合成为对外预测置信度。"""
    if (
        "low_stat_confidence" in flags
        or "estimated_stats" in flags
        or "runtime_target_unmatched" in flags
        or "special_damage_unmodeled" in flags
    ):
        return "low"
    if "uncalibrated_skill" in flags or "multi_hit" in flags or "runtime_effect_unmodeled" in flags:
        return "medium" if base == "high" else base
    return base


def validation_hint(flags: List[str]) -> Optional[str]:
    """把准确性标签转换为前端可展示的验证提示。"""
    hints = {
        "estimated_stats": "攻防属性来自估算，伤害可能偏差较大",
        "uncalibrated_skill": "技能尚未经过回放校准",
        "multi_hit": "多段/动态连击会放大预测误差",
        "energy_insufficient": "当前能量不足，预测仅供参考",
        "low_stat_confidence": "属性来源置信度较低",
        "runtime_target_unmatched": "服务端目标参数未能匹配当前目标",
        "runtime_effect_unmodeled": "存在尚未建模的运行时技能效果",
        "special_fixed_damage": "特殊固定/多段伤害，按专用规则评估",
        "special_damage_unmodeled": "特殊伤害规则尚未提交配置，预测仅供参考",
    }
    selected = [hints[flag] for flag in flags if flag in hints]
    return "；".join(selected) if selected else None
