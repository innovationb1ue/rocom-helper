"""性格数据查询。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.data.catalog import DATA_DIR, _read_json_dict

_nature_cache: Optional[Dict[str, Any]] = None
_nature_by_name_cache: Optional[Dict[str, Dict[str, Any]]] = None


def _load_nature_map() -> Dict[str, Any]:
    global _nature_cache
    if _nature_cache is not None:
        return _nature_cache
    path = DATA_DIR / "nature_map.json"
    _nature_cache = _read_json_dict(path)
    return _nature_cache


def get_nature(nature_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """按性格 ID 查找性格数据。"""
    if nature_id is None:
        return None
    return _load_nature_map().get(str(nature_id))


def get_nature_by_name(name: str) -> Optional[Dict[str, Any]]:
    """按性格名称查找性格数据。"""
    global _nature_by_name_cache
    if _nature_by_name_cache is None:
        _nature_by_name_cache = {}
        for value in _load_nature_map().values():
            n = value.get("name", "")
            if n:
                _nature_by_name_cache[n] = value
    return _nature_by_name_cache.get(name)


def get_nature_stat_modifiers(nature_id: Optional[int]) -> Dict[str, float]:
    """获取性格的属性修正，返回 {"atk": 0.1, "spa": -0.1, ...} 或空 dict。"""
    nature = get_nature(nature_id)
    if not nature:
        return {}
    mods = {}
    proportions = {
        "positive": nature.get("positive_effect_proportion", 0) or 0,
        "negative": nature.get("negative_effect_proportion", 0) or 0,
    }
    for attr_key, effect_field in [("positive", "positive_stat"), ("negative", "negative_stat")]:
        stat = nature.get(effect_field)
        if stat:
            val = proportions[attr_key] / 10000.0
            mods[stat] = mods.get(stat, 0.0) + (val if attr_key == "positive" else -val)

    return mods


def reset_nature_caches() -> None:
    global _nature_cache, _nature_by_name_cache
    _nature_cache = None
    _nature_by_name_cache = None
