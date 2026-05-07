"""技能评分系统 — 基于威力、能量效率、命中率等因子。"""
from __future__ import annotations

from typing import Dict, Optional


def score_skill(skill: Dict, type_chart=None) -> float:
    """综合评分 (0-100)。

    因子:
    - 威力 (weight: 30%)
    - 能量效率 (power / energy_cost) (weight: 20%)
    - 命中率 (weight: 15%)
    - PP 值 (weight: 10%)
    - 属性覆盖贡献 (weight: 15%)
    - 附加效果 (weight: 10%)
    """
    score = 0.0

    # 威力评分 (30%)
    power = skill.get("power") or 0
    if isinstance(power, str):
        try:
            power = int(power)
        except (ValueError, TypeError):
            power = 60  # variable power, assume average
    power_score = min(100.0, power / 200.0 * 100.0)
    score += power_score * 0.30

    # 能量效率评分 (20%)
    energy_cost = skill.get("energy_cost") or skill.get("energy") or 1
    if isinstance(energy_cost, str):
        try:
            energy_cost = int(energy_cost)
        except (ValueError, TypeError):
            energy_cost = 3
    if energy_cost > 0 and power > 0:
        efficiency = power / energy_cost
        eff_score = min(100.0, efficiency / 50.0 * 100.0)
    else:
        eff_score = 0.0
    score += eff_score * 0.20

    # 命中率评分 (15%)
    accuracy = skill.get("accuracy") or skill.get("hit_rate") or 100
    if isinstance(accuracy, str):
        try:
            accuracy = int(accuracy.rstrip("%"))
        except (ValueError, TypeError):
            accuracy = 100
    acc_score = min(100.0, accuracy / 100.0 * 100.0)
    score += acc_score * 0.15

    # PP 值评分 (10%)
    pp = skill.get("pp") or skill.get("max_pp") or 20
    if isinstance(pp, str):
        try:
            pp = int(pp)
        except (ValueError, TypeError):
            pp = 20
    pp_score = min(100.0, pp / 40.0 * 100.0)
    score += pp_score * 0.10

    # 属性覆盖贡献 (15%) — 如果提供了 type_chart，检查克制面
    skill_type = skill.get("type_id") or skill.get("attr_id")
    if type_chart and skill_type is not None:
        coverage = type_chart.get_coverage([skill_type])
        effective_count = sum(1 for m in coverage.values() if m >= 2.0)
        type_score = min(100.0, effective_count / 21.0 * 100.0)
    else:
        type_score = 50.0  # neutral
    score += type_score * 0.15

    # 附加效果 (10%)
    has_effect = bool(skill.get("effect") or skill.get("effect_desc") or
                      skill.get("buff_id") or skill.get("status_effect"))
    effect_score = 60.0 if has_effect else 30.0
    score += effect_score * 0.10

    return round(min(100.0, max(0.0, score)), 1)


def rank_skills(skills: list, type_chart=None) -> list:
    """给技能列表打分并按分数降序排列。返回 [{...skill, "_score": float}]。"""
    ranked = []
    for s in skills:
        sc = score_skill(s, type_chart)
        entry = dict(s)
        entry["_score"] = sc
        ranked.append(entry)
    ranked.sort(key=lambda x: x["_score"], reverse=True)
    return ranked
