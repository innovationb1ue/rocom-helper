"""Buff 速度和伤害减免修正计算。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.data.buff_effects import buff_stage, coerce_buff_id
from src.data.buff_tables import get_buff_damage_reduction_table, get_speed_buff_table


def get_speed_buff_modifiers(buff_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """从 buff 列表计算速度修正，返回 {"flat_total": float, "pct_total": float}。"""
    speed_buff_table = get_speed_buff_table()
    flat_total = 0.0
    pct_total = 0.0
    for buff in buff_list:
        buff_id = coerce_buff_id(buff)
        if buff_id is None:
            continue
        mods = speed_buff_table.get(buff_id)
        if not mods:
            continue
        stage = buff_stage(buff)
        flat_total += mods.get("flat", 0.0) * stage
        pct_total += mods.get("pct", 0.0) * stage
    return {"flat_total": flat_total, "pct_total": pct_total}


def get_buff_damage_reduction(
    buff_list: List[Dict[str, Any]], damage_type: int,
) -> float:
    """从 buff 列表计算总伤害减免比例，过滤指定伤害类型 (2=物理, 3=特殊)。"""
    damage_reduction_table = get_buff_damage_reduction_table()
    total = 0.0
    for buff in buff_list:
        buff_id = coerce_buff_id(buff)
        if buff_id is None:
            continue
        info = damage_reduction_table.get(buff_id)
        if not info:
            continue
        if damage_type not in info["damage_types"]:
            continue
        stage = buff_stage(buff)
        total += info["reduction"] * stage
    return min(0.95, total)
