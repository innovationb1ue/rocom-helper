"""技能伤害输入解析与威力修正。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.constants import SDT_TO_TYPE
from src.data.loader import get_buff_power_modifiers


def resolve_damage_type(skill_meta: Dict[str, Any]) -> int:
    """读取技能伤害类型。2=物攻，3=魔攻。"""
    return int(skill_meta.get("damage_type", 0) or 0)


def resolve_skill_element(skill_meta: Dict[str, Any]) -> int:
    """把协议 skill_dam_type 转换为游戏属性 ID。"""
    raw_dam_type = skill_meta.get("skill_dam_type", 0)
    return SDT_TO_TYPE.get(raw_dam_type, raw_dam_type)


def is_attack_skill(power: int, damage_type: int) -> bool:
    """判断技能是否可进入伤害公式。"""
    return power > 0 and damage_type in (2, 3)


def apply_buff_power_modifiers(
    power: int,
    attacker: Dict[str, Any],
    *,
    skill_element: int,
    skill_name: Any,
) -> int:
    """应用按技能属性/名称生效的固定威力 buff。"""
    modifiers = get_buff_power_modifiers(
        attacker.get("buffs", []),
        skill_element=skill_element,
        skill_name=skill_name,
    )
    if modifiers.get("flat"):
        return max(1, power + int(modifiers["flat"]))
    return power
