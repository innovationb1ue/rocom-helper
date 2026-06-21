"""Buff 属性修正计算。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from src.data.buff_effects import (
    TOP_LEVEL_SELECTOR_BUFF_IDS,
    buff_stage,
    collect_buff_ids,
    coerce_buff_id,
    iter_derived_buffs,
)
from src.data.buff_tables import get_buff_stat_table


def _merge_modifiers(target: Dict[str, float], source: Dict[str, float], factor: float = 1.0) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0.0) + value * factor


def _resolve_buff_modifiers(
    buff_id: int,
    *,
    include_children: bool,
    seen: Optional[Set[int]] = None,
) -> Dict[str, float]:
    """解析单个 buff 的属性修正。

    ``include_children`` 只在子效果已经明确时打开；折射本体这类 selector
    不能直接展开，否则会把所有系别效果同时加上。
    """
    buff_stat_table = get_buff_stat_table()
    seen = set(seen or set())
    if buff_id in seen:
        return {}
    seen.add(buff_id)

    result: Dict[str, float] = dict(buff_stat_table.get(buff_id) or {})
    if not include_children:
        return result

    for child_id in collect_buff_ids(buff_id, include_children=True)[1:]:
        _merge_modifiers(
            result,
            _resolve_buff_modifiers(child_id, include_children=False, seen=set(seen)),
        )
    return result


def get_buff_derived_stat_modifiers(buff_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """只计算 buff 字典中显式记录的 derived_buffs 属性修正。"""
    result: Dict[str, float] = {}
    for buff in buff_list:
        for child in iter_derived_buffs(buff):
            child_id = coerce_buff_id(child)
            if child_id is None:
                continue
            child_mods = _resolve_buff_modifiers(child_id, include_children=True)
            _merge_modifiers(result, child_mods, buff_stage(child))
    return result


def get_buff_stat_modifiers(buff_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """从 buff 列表解析属性修正，返回 {"atk_up": 0.2, "spa_down": 0.1, ...}。"""
    result: Dict[str, float] = {}
    for buff in buff_list:
        buff_id = coerce_buff_id(buff)
        if buff_id is None:
            continue
        include_children = buff_id not in TOP_LEVEL_SELECTOR_BUFF_IDS
        mods = _resolve_buff_modifiers(buff_id, include_children=include_children)
        if mods:
            _merge_modifiers(result, mods, buff_stage(buff))
        derived_mods = get_buff_derived_stat_modifiers([buff])
        if derived_mods:
            _merge_modifiers(result, derived_mods)
    return result
