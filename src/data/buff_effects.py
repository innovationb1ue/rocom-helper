"""Buff 效果树遍历和轻量字段归一化。"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

from src.data.buff_tables import get_buff_child_table

# 折射本体是按系别选择子效果的 selector，不能在没有协议上下文时展开所有子效果。
TOP_LEVEL_SELECTOR_BUFF_IDS = {20890020}


def coerce_buff_id(value: Any) -> Optional[int]:
    if isinstance(value, dict):
        value = value.get("id") or value.get("buff_id") or value.get("effect_id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def buff_stage(buff: Dict[str, Any]) -> int:
    try:
        return max(1, int(buff.get("stage", 1) or 1))
    except (TypeError, ValueError):
        return 1


def iter_derived_buffs(buff: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for item in buff.get("derived_buffs") or []:
        if isinstance(item, dict):
            yield item
        else:
            yield {"id": item}


def collect_buff_ids(
    buff_id: int,
    *,
    include_children: bool,
    seen: Optional[Set[int]] = None,
) -> List[int]:
    buff_child_table = get_buff_child_table()

    seen = set(seen or set())
    if buff_id in seen:
        return []
    seen.add(buff_id)

    ids = [buff_id]
    if not include_children:
        return ids
    for child_id in buff_child_table.get(buff_id, []):
        ids.extend(collect_buff_ids(child_id, include_children=True, seen=set(seen)))
    return ids


def collect_effective_buff_ids(
    buff_id: int,
    *,
    include_children: bool,
    root_id: Optional[int] = None,
    seen: Optional[Set[int]] = None,
) -> List[tuple[int, int]]:
    buff_child_table = get_buff_child_table()

    seen = set(seen or set())
    if buff_id in seen:
        return []
    seen.add(buff_id)
    root_id = root_id if root_id is not None else buff_id

    ids = [(buff_id, root_id)]
    if not include_children:
        return ids
    for child_id in buff_child_table.get(buff_id, []):
        ids.extend(
            collect_effective_buff_ids(
                child_id,
                include_children=True,
                root_id=root_id,
                seen=set(seen),
            )
        )
    return ids


def iter_effective_buff_ids(buff_list: List[Dict[str, Any]]) -> Iterable[tuple[int, int, Dict[str, Any]]]:
    for buff in buff_list:
        buff_id = coerce_buff_id(buff)
        if buff_id is None:
            continue
        include_children = buff_id not in TOP_LEVEL_SELECTOR_BUFF_IDS
        for item_id, root_id in collect_effective_buff_ids(buff_id, include_children=include_children):
            yield item_id, root_id, buff
        for child in iter_derived_buffs(buff):
            child_id = coerce_buff_id(child)
            if child_id is None:
                continue
            for item_id, root_id in collect_effective_buff_ids(child_id, include_children=True):
                yield item_id, root_id, child
