"""宠物物种数据和名称索引查询。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.data.catalog import DATA_DIR, _read_json_dict, get_bundle

_pet_species_cache: Optional[Dict[str, Any]] = None
_name_to_base_id_cache: Optional[Dict[str, int]] = None


def _load_pet_species() -> Dict[str, Any]:
    """加载 pet_species.json，以 base_id (str) 为 key。"""
    global _pet_species_cache
    if _pet_species_cache is not None:
        return _pet_species_cache
    path = DATA_DIR / "pet_species.json"
    _pet_species_cache = _read_json_dict(path)
    return _pet_species_cache


def get_pet_species(base_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """按 base_id 查找宠物物种数据（种族值、属性、特性等）。"""
    if base_id is None:
        return None
    return _load_pet_species().get(str(base_id))


def get_pet_species_stats(base_id: Optional[int]) -> Dict[str, int]:
    """按 base_id 查找宠物种族值。"""
    sp = get_pet_species(base_id)
    if sp and sp.get("stats"):
        return sp["stats"]
    return {}


def get_pet_species_types(base_id: Optional[int]) -> List[int]:
    """按 base_id 查找宠物属性类型 ID 列表。"""
    sp = get_pet_species(base_id)
    if sp and sp.get("types"):
        return sp["types"]
    return []


def get_pet_implemented(base_id: Optional[int]) -> bool:
    """按 base_id 判断宠物是否已实装。"""
    sp = get_pet_species(base_id)
    if sp:
        return bool(sp.get("implemented", False))
    return False


def _build_name_to_base_id() -> Dict[str, int]:
    """从 pet_map.json 构建宠物名 → base_id 索引。同名取第一个。"""
    global _name_to_base_id_cache
    if _name_to_base_id_cache is not None:
        return _name_to_base_id_cache
    _name_to_base_id_cache = {}
    pet_map = get_bundle().get("pet_meta", {})
    for pid, entry in pet_map.items():
        name = entry.get("name") or entry.get("species_name")
        if isinstance(name, str) and name:
            _name_to_base_id_cache.setdefault(name, entry.get("base_id", pid))
    return _name_to_base_id_cache


def get_base_id_by_name(name: str) -> Optional[int]:
    """按宠物名查找 base_id。"""
    if not name:
        return None
    return _build_name_to_base_id().get(name)


def get_species_by_name(name: str) -> Optional[Dict[str, Any]]:
    """按宠物名查找物种数据（组合查询：name → base_id → pet_species）。"""
    base_id = get_base_id_by_name(name)
    if base_id is None:
        return None
    return get_pet_species(base_id)


def get_pet_types_from_species(base_id: Optional[int]) -> List[int]:
    """从 pet_species 获取属性 ID。"""
    types = get_pet_species_types(base_id)
    if types:
        return types
    return []


def reset_pet_species_caches() -> None:
    global _pet_species_cache, _name_to_base_id_cache
    _pet_species_cache = None
    _name_to_base_id_cache = None
