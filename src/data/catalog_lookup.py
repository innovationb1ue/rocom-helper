"""基础 catalog 元数据和名称查询。"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from src.data.catalog_bundle import get_bundle, get_maps

_MetaNormalizer = Callable[[Optional[int]], Optional[int]]


def _normalize_skill_id(value: Optional[int]) -> Optional[int]:
    if value is None or value <= 0:
        return None
    return value // 100 if value >= 100_000 and value % 100 == 0 else value


def _normalize_lookup_value(
    value: Optional[int],
    *,
    normalizer: Optional[_MetaNormalizer] = None,
) -> Optional[int]:
    if value is None:
        return None
    normalized = normalizer(value) if normalizer else value
    if normalized is None:
        return None
    return int(normalized)


def _get_bundle_meta(
    *bundle_keys: str,
    value: Optional[int],
    normalizer: Optional[_MetaNormalizer] = None,
) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    bundle = get_bundle()
    # 先按原始 ID 查找，避免把合法的大 ID 误归一化到另一个条目。
    for bundle_key in bundle_keys:
        entry = bundle.get(bundle_key, {}).get(value)
        if isinstance(entry, dict):
            return entry
    if normalizer:
        normalized = normalizer(value)
        if normalized is not None and normalized != value:
            for bundle_key in bundle_keys:
                entry = bundle.get(bundle_key, {}).get(normalized)
                if isinstance(entry, dict):
                    return entry
    return None


def _get_name_from_meta_or_map(
    *bundle_keys: str,
    value: Optional[int],
    map_name: Optional[str] = None,
    normalizer: Optional[_MetaNormalizer] = None,
) -> Optional[str]:
    meta = _get_bundle_meta(*bundle_keys, value=value, normalizer=normalizer)
    if meta and isinstance(meta.get("name"), str):
        return meta["name"]
    if map_name is None:
        return None
    maps = get_maps()
    name = maps[map_name].get(value)
    if name:
        return name
    if normalizer:
        normalized = normalizer(value)
        if normalized is not None and normalized != value:
            return maps[map_name].get(normalized)
    return None


def get_attr_meta(attr_id: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("attr_meta", value=attr_id)


def get_attr_name(attr_id: Optional[int]) -> Optional[str]:
    return _get_name_from_meta_or_map("attr_meta", value=attr_id, map_name="attr")


def get_skill_meta(skill_id: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("skill_meta", value=skill_id, normalizer=_normalize_skill_id)


def get_skill_name(skill_id: Optional[int]) -> Optional[str]:
    return _get_name_from_meta_or_map(
        "skill_meta",
        value=skill_id,
        map_name="skill",
        normalizer=_normalize_skill_id,
    )


def get_buff_meta(buff_id: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("buff_meta", value=buff_id)


def get_buffbase_meta(buffbase_id: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("buffbase_meta", value=buffbase_id)


def get_pet_meta(pet_id: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("pet_meta", "monster_meta", value=pet_id)


def get_pet_name(pet_id: Optional[int]) -> Optional[str]:
    return _get_name_from_meta_or_map("pet_meta", "monster_meta", value=pet_id, map_name="pet")


def get_opcode_pb_meta(opcode: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("opcode_pb_meta", value=opcode)


def get_pb_message_meta(name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    value = get_bundle().get("pb_message_meta", {}).get(name)
    return value if isinstance(value, dict) else None
