"""技能效果分类器 — 从 skill_meta 解析技能效果标签。

用于 TacticalEngine 对非伤害技能进行结构化评分。
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

from src.data.loader import get_buff_meta, get_buffbase_meta

# attr_id → 效果标签映射（扩展自 loader._ATTR_TO_STAT_KEY）
_ATTR_TO_TAG = {
    1: "hp", 25: "hp",
    6: "speed",
    17: "atk_up", 29: "atk_up", 33: "atk_down",
    18: "spa_up", 30: "spa_up", 34: "spa_down",
    19: "def_up", 31: "def_up", 35: "def_down",
    20: "spd_up", 32: "spd_up", 36: "spd_down",
    21: "damage_boost",
    22: "damage_reduce",
    37: "effectiveness_boost",
    38: "effectiveness_reduce",
}

# 描述关键词 → 标签
_DESC_KEYWORDS = {
    "heal": {"恢复", "治疗", "回血", "回复", "治愈", "疗愈"},
    "shield": {"护盾", "保护", "盾", "抵挡", "防御姿态"},
    "weather": {"天气", "气候", "环境"},
    "hazard": {"毒", "灼烧", "麻痹", "睡眠", "冰冻", "混乱", "诅咒"},
    "cleanse": {"清除", "净化", "解除", "驱散"},
    "priority": {"先手", "优先", "迅捷"},
    "speed": {"速度", "加速"},
    "stat_up": {"强化", "提升"},
    "stat_down": {"削弱", "降低"},
}


def classify_skill_effect(skill_meta: Dict[str, Any]) -> List[str]:
    """对技能 meta 进行分类，返回效果标签列表。

    标签包括:
      - stat_up / stat_down / heal / shield / speed / weather / hazard / cleanse / priority
      - 具体属性: atk_up, spa_up, def_up, spd_up, atk_down, spa_down, def_down, spd_down
      - damage_boost / damage_reduce / effectiveness_boost / effectiveness_reduce
    """
    tags: Set[str] = set()

    # 1. 从 skill_result 的 effect_id 反查 buff
    results = skill_meta.get("skill_result", [])
    for result in results:
        effect_id = result.get("effect_id")
        if effect_id is None:
            continue
        buff = get_buff_meta(effect_id)
        if not buff:
            continue
        base_ids = buff.get("buff_base_ids", [])
        for bb_id in base_ids:
            bb = get_buffbase_meta(bb_id)
            if not bb:
                continue
            params = bb.get("buffbase_param", [])
            if not params:
                continue
            try:
                attr_id = params[0].get("params", [None])[0]
            except (IndexError, AttributeError):
                continue
            tag = _ATTR_TO_TAG.get(attr_id)
            if tag:
                tags.add(tag)
                # 聚合到 stat_up / stat_down
                if tag in ("atk_up", "spa_up", "def_up", "spd_up"):
                    tags.add("stat_up")
                elif tag in ("atk_down", "spa_down", "def_down", "spd_down"):
                    tags.add("stat_down")
                elif tag == "speed":
                    tags.add("stat_up")

    # 2. 从描述中提取关键词
    desc = (skill_meta.get("desc") or "").lower()
    for tag, keywords in _DESC_KEYWORDS.items():
        for kw in keywords:
            if kw in desc:
                tags.add(tag)
                break

    # 3. 特殊判断: dam_para[0] == 0 但 damage_type == 2/3 可能是 "无威力攻击"
    dam_para = skill_meta.get("dam_para", [])
    damage_type = skill_meta.get("damage_type", 0)
    if not tags and ((not dam_para or dam_para[0] == 0) or damage_type not in (2, 3)):
        tags.add("other")

    return sorted(tags)


def is_heal_skill(skill_meta: Dict[str, Any]) -> bool:
    return "heal" in classify_skill_effect(skill_meta)


def is_stat_up_skill(skill_meta: Dict[str, Any]) -> bool:
    return "stat_up" in classify_skill_effect(skill_meta)


def is_speed_skill(skill_meta: Dict[str, Any]) -> bool:
    tags = classify_skill_effect(skill_meta)
    return "speed" in tags or "spd_up" in tags or "priority" in tags
