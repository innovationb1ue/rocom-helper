"""Cached lookup tables for buff-derived combat modifiers."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.data.catalog import get_bundle

logger = logging.getLogger(__name__)

# attr_map ID -> stat modifier key
_ATTR_TO_STAT_KEY = {
    17: "atk_up", 18: "spa_up",
    29: "atk_up", 30: "spa_up", 31: "def_up", 32: "spd_up",
    33: "atk_down", 34: "spa_down", 35: "def_down", 36: "spd_down",
}

# 某些 attr_id 的值存储在 params[4] 而非 params[2]
_ATTR_USING_PARAM4 = {17, 18}

_SPEED_STAT_PARAM = 6  # buffbase params[0] = 6 表示速度

_buff_stat_cache: Optional[Dict[int, Dict[str, float]]] = None
_buff_child_cache: Optional[Dict[int, List[int]]] = None
_speed_buff_cache: Optional[Dict[int, Dict[str, float]]] = None
_buff_dmg_reduce_cache: Optional[Dict[int, Dict[str, Any]]] = None


def _build_buff_stat_table() -> Dict[int, Dict[str, float]]:
    """从 buff_map.json -> buffbase_map.json 构建 buff_id -> 属性修正映射。"""
    bundle = get_bundle()
    buff_meta = bundle.get("buff_meta", {})
    buffbase_meta = bundle.get("buffbase_meta", {})

    table: Dict[int, Dict[str, float]] = {}
    for buff_id, buff_entry in buff_meta.items():
        base_ids = buff_entry.get("buff_base_ids") or []
        if not base_ids:
            continue
        mods: Dict[str, float] = {}
        for bb_id in base_ids:
            bb = buffbase_meta.get(bb_id)
            if not bb:
                continue
            params_list = bb.get("buffbase_param", [])
            if len(params_list) < 3:
                continue
            try:
                attr_id = params_list[0].get("params", [None])[0]
                raw_val = params_list[2].get("params", [None])[0]
                if (raw_val == 0 or raw_val is None) and attr_id in _ATTR_USING_PARAM4 and len(params_list) >= 5:
                    raw_val = params_list[4].get("params", [None])[0]
                value = raw_val
            except (IndexError, AttributeError):
                continue
            if attr_id is None or value is None:
                continue
            stat_key = _ATTR_TO_STAT_KEY.get(attr_id)
            if stat_key:
                mods[stat_key] = mods.get(stat_key, 0.0) + value / 10000.0
            else:
                logger.debug("Unmapped buff attr_id %s in buffbase %s (buff %s)", attr_id, bb_id, buff_id)
        if mods:
            table[buff_id] = mods
    return table


def _build_buff_child_table() -> Dict[int, List[int]]:
    """构建 buff_id -> 子 buff ids，用于显式派生 buff 的递归展开。"""
    bundle = get_bundle()
    buff_meta = bundle.get("buff_meta", {})
    buffbase_meta = bundle.get("buffbase_meta", {})
    known_buff_ids = set(buff_meta.keys())

    table: Dict[int, List[int]] = {}
    for buff_id, buff_entry in buff_meta.items():
        children: List[int] = []
        for bb_id in buff_entry.get("buff_base_ids") or []:
            bb = buffbase_meta.get(bb_id)
            if not bb:
                continue
            for param in bb.get("buffbase_param", []) or []:
                for raw in param.get("params", []) or []:
                    try:
                        child_id = int(raw)
                    except (TypeError, ValueError):
                        continue
                    if child_id != buff_id and child_id in known_buff_ids:
                        children.append(child_id)
        if children:
            table[buff_id] = children
    return table


def _build_speed_buff_table() -> Dict[int, Dict[str, float]]:
    """从 buff_map.json -> buffbase_map.json 构建 buff_id -> 速度修正映射。

    buffbase param 结构 (params 按 3 个一组):
      params[0] = 6 (速度属性标识)
      params[1] = 0 -> 固定值修改, params[2] = +/-N
      params[1] = 1 -> 百分比修改, params[2] = N (N/10000)
    """
    bundle = get_bundle()
    buff_meta = bundle.get("buff_meta", {})
    buffbase_meta = bundle.get("buffbase_meta", {})

    table: Dict[int, Dict[str, float]] = {}
    for buff_id, buff_entry in buff_meta.items():
        base_ids = buff_entry.get("buff_base_ids") or []
        if not base_ids:
            continue
        flat = 0.0
        pct = 0.0
        for bb_id in base_ids:
            bb = buffbase_meta.get(bb_id)
            if not bb:
                continue
            params_list = bb.get("buffbase_param", [])
            for i in range(0, len(params_list) - 2, 3):
                try:
                    p0 = params_list[i].get("params", [None])[0]
                    p1 = params_list[i + 1].get("params", [None])[0]
                    p2 = params_list[i + 2].get("params", [None])[0]
                except (IndexError, AttributeError):
                    continue
                if p0 != _SPEED_STAT_PARAM or p2 is None:
                    continue
                if p1 == 0:
                    flat += p2
                elif p1 == 1:
                    pct += p2 / 10000.0
        if flat != 0 or pct != 0:
            table[buff_id] = {"flat": flat, "pct": pct}
    return table


def _build_buff_damage_reduction_table() -> Dict[int, Dict[str, Any]]:
    """从 buff_map.json -> buffbase_map.json 构建 buff_id -> 伤害减免映射。

    buffbase param 结构:
      params[1] = 伤害类型过滤 ([2]=物理, [3]=特殊, [2,3]=全部)
      params[4] = 减免值 (负数, /10000, 如 -8000 = 80% 减免)
    """
    bundle = get_bundle()
    buff_meta = bundle.get("buff_meta", {})
    buffbase_meta = bundle.get("buffbase_meta", {})

    table: Dict[int, Dict[str, Any]] = {}
    for buff_id, buff_entry in buff_meta.items():
        base_ids = buff_entry.get("buff_base_ids") or []
        if not base_ids:
            continue
        total_reduction = 0.0
        dmg_types: set[int] = set()
        for bb_id in base_ids:
            bb = buffbase_meta.get(bb_id)
            if not bb:
                continue
            params_list = bb.get("buffbase_param", [])
            if len(params_list) < 5:
                continue
            try:
                type_filter = params_list[1].get("params", [])
                reduce_val = params_list[4].get("params", [0])[0]
            except (IndexError, AttributeError):
                continue
            if reduce_val >= 0:
                continue
            total_reduction += abs(reduce_val) / 10000.0
            dmg_types.update(type_filter)
        if total_reduction > 0:
            table[buff_id] = {
                "reduction": total_reduction,
                "damage_types": sorted(dmg_types),
            }
    return table


def get_buff_stat_table() -> Dict[int, Dict[str, float]]:
    global _buff_stat_cache
    if _buff_stat_cache is None:
        _buff_stat_cache = _build_buff_stat_table()
    return _buff_stat_cache


def get_buff_child_table() -> Dict[int, List[int]]:
    global _buff_child_cache
    if _buff_child_cache is None:
        _buff_child_cache = _build_buff_child_table()
    return _buff_child_cache


def get_speed_buff_table() -> Dict[int, Dict[str, float]]:
    global _speed_buff_cache
    if _speed_buff_cache is None:
        _speed_buff_cache = _build_speed_buff_table()
    return _speed_buff_cache


def get_buff_damage_reduction_table() -> Dict[int, Dict[str, Any]]:
    global _buff_dmg_reduce_cache
    if _buff_dmg_reduce_cache is None:
        _buff_dmg_reduce_cache = _build_buff_damage_reduction_table()
    return _buff_dmg_reduce_cache


def reset_buff_tables() -> None:
    global _buff_stat_cache, _buff_child_cache, _speed_buff_cache, _buff_dmg_reduce_cache
    _buff_stat_cache = None
    _buff_child_cache = None
    _speed_buff_cache = None
    _buff_dmg_reduce_cache = None
