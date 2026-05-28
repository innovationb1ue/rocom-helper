"""游戏静态数据 catalog 与基础缓存。

本模块只负责 JSON bundle 的读取、ID 规范化和元数据查询。更高层的
buff、物种、预设等领域逻辑应通过 ``loader.py`` 兼容门面导出，避免
所有数据访问逻辑继续堆在一个文件里。
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.config import settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = settings.project_root
DATA_DIR = settings.data_dir

_JSON_PATHS: Dict[str, Path] = {
    "attr_meta": DATA_DIR / "attr_map.json",
    "skill_meta": DATA_DIR / "skill_map.json",
    "buff_meta": DATA_DIR / "buff_map.json",
    "buffbase_meta": DATA_DIR / "buffbase_map.json",
    "pet_meta": DATA_DIR / "pet_map.json",
    "monster_meta": DATA_DIR / "monster_map.json",
    "pet_skill_meta": DATA_DIR / "pet_skill_map.json",
    "monster_skillbank_meta": DATA_DIR / "monster_skillbank_map.json",
    "special_move_meta": DATA_DIR / "special_move_map.json",
    "opcode_pb_meta": DATA_DIR / "opcode_pb_map.json",
    "pb_message_meta": DATA_DIR / "pb_message_index.json",
    "innate_skills": DATA_DIR / "innate_skills.json",
}

_json_cache: Optional[Dict[str, Any]] = None
_maps_cache: Optional[Dict[str, Dict[int, str]]] = None
_lock = threading.RLock()

_MetaNormalizer = Callable[[Optional[int]], Optional[int]]


def _safe_int(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    s = text.strip()
    try:
        return int(s, 10) if s else None
    except ValueError:
        return None


def _normalize_skill_id(value: Optional[int]) -> Optional[int]:
    if value is None or value <= 0:
        return None
    return value // 100 if value >= 100_000 and value % 100 == 0 else value


def _read_json_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load JSON data %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _int_keyed_meta(raw: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for key, value in raw.items():
        try:
            ikey = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            out[ikey] = value
    return out


def _name_map_from_meta(meta: Dict[int, Dict[str, Any]]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for key, value in meta.items():
        name = value.get("name")
        if isinstance(name, str) and name:
            out[key] = name
    return out


def _load_json_bundle() -> Dict[str, Any]:
    bundle: Dict[str, Any] = {}
    for name, path in _JSON_PATHS.items():
        raw = _read_json_dict(path)
        if name == "pb_message_meta":
            bundle[name] = raw
        else:
            bundle[name] = _int_keyed_meta(raw)
    return bundle


def get_bundle() -> Dict[str, Any]:
    global _json_cache
    if _json_cache is not None:
        return _json_cache
    with _lock:
        if _json_cache is None:
            _json_cache = _load_json_bundle()
    return _json_cache


def _load_all_maps() -> Dict[str, Dict[int, str]]:
    bundle = get_bundle()
    attr_map = _name_map_from_meta(bundle.get("attr_meta", {}))
    pet_map = _name_map_from_meta(bundle.get("pet_meta", {}))
    skill_map = _name_map_from_meta(bundle.get("skill_meta", {}))
    return {"attr": attr_map, "pet": pet_map, "skill": skill_map}


def get_maps() -> Dict[str, Dict[int, str]]:
    global _maps_cache
    if _maps_cache is not None:
        return _maps_cache
    with _lock:
        if _maps_cache is None:
            _maps_cache = _load_all_maps()
    return _maps_cache


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


def invalidate_catalog_cache() -> None:
    """清理基础 bundle/name-map 缓存，供 loader 统一缓存失效调用。"""
    global _json_cache, _maps_cache
    with _lock:
        _json_cache = None
        _maps_cache = None
