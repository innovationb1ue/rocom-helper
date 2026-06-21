"""战术行动推荐理由文案。"""
from __future__ import annotations

from typing import Any, Dict

HIGH_DAMAGE_HP_APPROX = 300
HIGH_DAMAGE_RATIO = 0.5


def generate_reason(
    our_action: Dict[str, Any],
    damage_dealt: int,
    damage_taken: int,
    can_ko: bool,
) -> str:
    """生成中文推荐理由。"""
    if our_action["action_type"] == "switch":
        return switch_reason(our_action, damage_taken, can_ko)
    return skill_reason(our_action, damage_dealt, damage_taken, can_ko)


def switch_reason(
    our_action: Dict[str, Any],
    damage_taken: int,
    can_ko: bool,
) -> str:
    name = our_action.get("switch_to_name", "?")
    reasons = []
    if can_ko is False and damage_taken > 0:
        reasons.append(f"吃 {damage_taken} 伤害")
    reasons.append("改善对位")
    return f"换上 {name}，{'，'.join(reasons)}"


def skill_reason(
    our_action: Dict[str, Any],
    damage_dealt: int,
    damage_taken: int,
    can_ko: bool,
) -> str:
    skill_name = our_action.get("skill_name", "?")
    reasons = []

    if can_ko:
        reasons.append("先手击杀")
    if damage_dealt > 0:
        if is_high_damage(damage_dealt):
            reasons.append("高伤害")
        else:
            reasons.append(f"{damage_dealt} 伤害")

    energy_cost = our_action.get("energy_cost", 0)
    if energy_cost >= 5:
        reasons.append(f"耗能 {energy_cost}")

    if damage_taken > 0:
        reasons.append(f"承受 {damage_taken}")

    return f"{skill_name}：{'，'.join(reasons)}" if reasons else skill_name


def is_high_damage(damage_dealt: int) -> bool:
    return damage_dealt > HIGH_DAMAGE_HP_APPROX * HIGH_DAMAGE_RATIO
