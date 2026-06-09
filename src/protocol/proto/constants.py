"""协议层游戏常量和枚举映射。"""
from __future__ import annotations

from typing import Dict, Tuple

STAT_NAMES = ["HP", "ATK", "DEF", "SPA", "SPD", "SPE"]
SIDE_NAMES: Dict[int, str] = {1: "我方", 401: "敌方"}
_WILLPOWER_SKILL_ID = 7700014
_ENERGY_BOTTLE_MAX = 10
SPECIAL_ACTION_COMMANDS: Dict[Tuple[int, int], str] = {
    (8, 7): "愿力强化", (3, 8): "能量瓶", (2, 9): "换人",
}
SPECIAL_ACTION_SHAPES: Dict[Tuple[int, int], str] = {
    (8, 8): "愿力强化", (3, 4): "能量瓶", (2, 3): "换人",
}

# SkillDamType enum values (proto_schema PetData.skill_dam_type) → elemental type ID.
# The battle protocol sends SkillDamType enum values in field 6, not type IDs directly.
SDT_TO_TYPE: Dict[int, int] = {
    2: 0,   # SDT_COMMON → 普通
    3: 3,   # SDT_GRASS → 草
    4: 1,   # SDT_FIRE → 火
    5: 2,   # SDT_WATER → 水
    6: 17,  # SDT_LIGHT → 光
    7: 8,   # SDT_EARTH → 地
    9: 5,   # SDT_ICE → 冰
    10: 15, # SDT_DRAGON → 龙
    11: 4,  # SDT_ELECTRIC → 电
    12: 7,  # SDT_TOXIC → 毒
    13: 12, # SDT_INSECT → 虫
    14: 6,  # SDT_FIGHT → 武
    15: 9,  # SDT_WING → 翼
    16: 10, # SDT_MOE → 萌
    17: 13, # SDT_GHOST → 幽
    18: 16, # SDT_DEMON → 恶
    19: 14, # SDT_MECHANIC → 机械
    20: 11, # SDT_PHANTOM → 幻
    23: 0,  # SDT_GENERAL → 普通
}

