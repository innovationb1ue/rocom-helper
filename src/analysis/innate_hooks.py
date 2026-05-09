"""先天技能伤害计算 hook — 基于 innate_skills.json 定义实现 combo/stat/type/power 修正。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.data.loader import get_innate_skill


def _get_active_innate_skills(pet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 pet 的 buffs 中查找所有激活的先天技能定义。"""
    skills: List[Dict[str, Any]] = []
    for buff in pet.get("buffs", []):
        buff_id = buff.get("id")
        if buff_id is not None:
            innate = get_innate_skill(buff_id)
            if innate is not None:
                skills.append(innate)
    return skills


# ---------------------------------------------------------------------------
# combo_modify hook  (post_calc stage)
# ---------------------------------------------------------------------------


def combo_modify_hook(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """连击修正 — 根据先天技能增加连击次数，总伤害 = 单次伤害 × 连击总数。"""
    attacker = ctx.get("attacker", {})
    defender = ctx.get("defender", {})
    combo_bonus = attacker.get("combo_bonus", 0)

    if combo_bonus <= 0:
        return ctx

    additive_bonus = 0
    multiplier = 1

    for skill in _get_active_innate_skills(attacker):
        if skill.get("effect_type") != "combo_modify":
            continue
        params = skill.get("effect_params", {})
        trigger = params.get("trigger", "always")

        if trigger == "always":
            mult = params.get("multiplier", 0)
            if mult > 1:
                multiplier = max(multiplier, mult)
            else:
                additive_bonus += params.get("value", 0)
        elif trigger == "per_poison_stack":
            stacks = defender.get("poison_stacks", 0)
            additive_bonus += params.get("value", 0) * stacks
        elif trigger == "skill_element_used":
            element = params.get("element")
            skill_element = ctx.get("skill_meta", {}).get("skill_dam_type", 0)
            if skill_element == element:
                additive_bonus += params.get("value", 0)

    total_hits = int(combo_bonus * multiplier + additive_bonus)
    if total_hits > 1:
        ctx["hit_count"] = total_hits
        ctx["min_damage"] = int(ctx["min_damage"] * total_hits)
        ctx["max_damage"] = int(ctx["max_damage"] * total_hits)

    return ctx


# ---------------------------------------------------------------------------
# stat_modify hook  (post_base stage)
# ---------------------------------------------------------------------------


def stat_modify_hook(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """属性修正 — 满足条件时按百分比提升基础伤害。"""
    attacker = ctx.get("attacker", {})

    total_modifier = 0.0
    for skill in _get_active_innate_skills(attacker):
        if skill.get("effect_type") != "stat_modify":
            continue
        params = skill.get("effect_params", {})
        trigger = params.get("trigger")

        if trigger == "hp_below":
            threshold = params.get("threshold_pct", 0) / 100.0
            current_hp = attacker.get("current_hp", 0)
            max_hp = attacker.get("max_hp", 1) or 1
            if current_hp / max_hp <= threshold:
                total_modifier += params.get("modifier_pct", 0) / 100.0

    if total_modifier > 0:
        ctx["base_damage"] = max(1, int(ctx["base_damage"] * (1 + total_modifier)))

    return ctx


# ---------------------------------------------------------------------------
# type_resist_modify hook  (pre_final stage)
# ---------------------------------------------------------------------------


def type_resist_modify_hook(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """属性抵抗修正 — 将属性克制倍率下限提升至指定值（如无视抵抗 → 最低 1.0）。"""
    attacker = ctx.get("attacker", {})

    min_eff = 0.0
    for skill in _get_active_innate_skills(attacker):
        if skill.get("effect_type") != "type_resist_modify":
            continue
        params = skill.get("effect_params", {})
        min_eff = max(min_eff, params.get("min_effectiveness", 0.0))

    if min_eff > 0 and ctx.get("effectiveness", 0) < min_eff:
        ctx["effectiveness"] = min_eff

    return ctx


# ---------------------------------------------------------------------------
# power_modify hook  (post_calc stage)
# ---------------------------------------------------------------------------


def power_modify_hook(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """威力修正 — 附加吸血等效果，将元数据写入 context 供上层消费。"""
    attacker = ctx.get("attacker", {})

    for skill in _get_active_innate_skills(attacker):
        if skill.get("effect_type") != "power_modify":
            continue
        params = skill.get("effect_params", {})
        trigger = params.get("trigger")

        if trigger == "first_strike" and attacker.get("first_strike"):
            lifesteal = params.get("lifesteal_pct", 0)
            if lifesteal > 0:
                ctx["lifesteal_pct"] = ctx.get("lifesteal_pct", 0) + lifesteal
                heal = int(ctx["max_damage"] * lifesteal / 100)
                ctx["lifesteal_heal"] = ctx.get("lifesteal_heal", 0) + heal

    return ctx


# ---------------------------------------------------------------------------
# 便捷注册
# ---------------------------------------------------------------------------


def register_innate_hooks(calculator: Any) -> None:
    """将四个先天技能 hook 注册到 DamageCalculator 实例。"""
    calculator.register_hook("post_base", stat_modify_hook)
    calculator.register_hook("pre_final", type_resist_modify_hook)
    calculator.register_hook("post_calc", combo_modify_hook)
    calculator.register_hook("post_calc", power_modify_hook)
