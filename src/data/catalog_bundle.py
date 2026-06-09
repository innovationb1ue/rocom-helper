"""基础 JSON bundle 和名称映射缓存。"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from src.data.catalog_files import _JSON_PATHS, _read_json_dict

_json_cache: Optional[Dict[str, Any]] = None
_maps_cache: Optional[Dict[str, Dict[int, str]]] = None
_lock = threading.RLock()


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


def invalidate_catalog_cache() -> None:
    """清理基础 bundle/name-map 缓存，供 loader 统一缓存失效调用。"""
    global _json_cache, _maps_cache
    with _lock:
        _json_cache = None
        _maps_cache = None
