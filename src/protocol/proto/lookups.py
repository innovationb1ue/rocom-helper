"""协议 detail 构建时使用的名称查找和侧边辅助。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.data.loader import (
    get_attr_name,
    get_buff_meta,
    get_buffbase_meta,
    get_pet_name,
    get_skill_name,
)
from src.protocol.proto.constants import SIDE_NAMES
from src.protocol.proto.tree import collect_varints, pick_first


def normalize_skill_id(v: Optional[int]) -> Optional[int]:
    if v is None:
        return None
    if v >= 10_000_000 and v % 100 == 0:
        candidate = v // 100
        return candidate if get_skill_name(candidate) else candidate
    if get_skill_name(v):
        return v
    return v


def skill_name(skill_id: Optional[int]) -> Optional[str]:
    return get_skill_name(skill_id)


def type_name(type_id: Optional[int]) -> Optional[str]:
    return get_attr_name(type_id)


def pet_name_fn(pet_id: Optional[int]) -> Optional[str]:
    return get_pet_name(pet_id)


def buff_name(buff_id: Optional[int]) -> Optional[str]:
    meta = get_buff_meta(buff_id)
    if not isinstance(meta, dict):
        return None
    if isinstance(meta.get("name"), str) and meta["name"]:
        return meta["name"]
    if isinstance(meta.get("editor_name"), str) and meta["editor_name"]:
        return meta["editor_name"]
    return None


def side_name(side_id: Optional[int]) -> Optional[str]:
    if side_id is None:
        return None
    v = int(side_id)
    if v in SIDE_NAMES:
        return SIDE_NAMES[v]
    # Extended IDs: 1-6 = player slots, 401-406 = opponent slots
    if v >= 401:
        return "敌方"
    if 1 <= v <= 6:
        return "我方"
    return None


def _attach_buff_meta(out: Dict[str, Any], buff_id: Optional[int]) -> None:
    if buff_id is None:
        return
    name = buff_name(buff_id)
    if name and not out.get("effect_name"):
        out["effect_name"] = name


def _attach_buffbase_meta(out: Dict[str, Any], base_id: Optional[int]) -> None:
    if base_id is None:
        return
    meta = get_buffbase_meta(base_id)
    if isinstance(meta, dict) and meta.get("name") and not out.get("effect_base_name"):
        out["effect_base_name"] = meta["name"]


def _extract_actor_target(msg: Dict[str, Any], out: Dict[str, Any]) -> None:
    actor = pick_first(collect_varints(msg, 1))
    target = pick_first(collect_varints(msg, 2))
    out["actor_side"] = actor
    out["actor_side_name"] = side_name(actor)
    out["target_side"] = target
    out["target_side_name"] = side_name(target)

