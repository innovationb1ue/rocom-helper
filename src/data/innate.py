"""先天技能和精灵特性数据查询。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.data.catalog import _JSON_PATHS, _int_keyed_meta, get_bundle
from src.data.pet_species import _load_pet_species

_innate_skills_cache: Optional[Dict[int, Dict[str, Any]]] = None
_pet_trait_cache: Optional[Dict[str, Dict[str, str]]] = None


def _load_innate_skills() -> Dict[int, Dict[str, Any]]:
    """加载 innate_skills.json，以 buff_id (int) 为 key 返回 skills 字典。"""
    global _innate_skills_cache
    if _innate_skills_cache is not None:
        return _innate_skills_cache
    path = _JSON_PATHS["innate_skills"]
    if not path.exists():
        _innate_skills_cache = {}
        return _innate_skills_cache
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        _innate_skills_cache = {}
        return _innate_skills_cache
    raw_skills = data.get("skills", {}) if isinstance(data, dict) else {}
    _innate_skills_cache = _int_keyed_meta(raw_skills)
    return _innate_skills_cache


def get_innate_skill(buff_id: int) -> Optional[Dict[str, Any]]:
    """按 buff_id 查找先天技能效果定义。"""
    return _load_innate_skills().get(buff_id)


def _load_pet_traits() -> Dict[str, Dict[str, str]]:
    """加载精灵名到先天特性的索引。"""
    global _pet_trait_cache
    if _pet_trait_cache is not None:
        return _pet_trait_cache
    _pet_trait_cache = {}
    skill_map = get_bundle().get("skill_meta", {})
    species_map = _load_pet_species()
    for sp in species_map.values():
        name = sp.get("name", "")
        if not name or name in _pet_trait_cache:
            continue
        feature_id = sp.get("pet_feature")
        if not feature_id:
            continue
        skill = skill_map.get(feature_id)
        if not skill:
            continue
        trait_name = skill.get("name", "")
        if not trait_name:
            continue
        _pet_trait_cache[name] = {
            "name": trait_name,
            "description": skill.get("desc", ""),
        }
    return _pet_trait_cache


def get_pet_innate_trait(pet_name: str) -> Optional[Dict[str, str]]:
    """按精灵名查找先天特性（来自 pet_species.pet_feature → skill_map）。"""
    return _load_pet_traits().get(pet_name)


def get_innate_skills_for_pet(base_id: int) -> List[Dict[str, Any]]:
    """按 base_id 查找精灵的先天技能列表。"""
    path = _JSON_PATHS["innate_skills"]
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []
    pets = data.get("pets", {}) if isinstance(data, dict) else {}
    pet_skills = pets.get(str(base_id), [])
    if not isinstance(pet_skills, list):
        return []
    result = []
    for buff_id in pet_skills:
        skill = get_innate_skill(buff_id)
        if skill is not None:
            result.append(skill)
    return result


def reset_innate_caches() -> None:
    global _innate_skills_cache, _pet_trait_cache
    _innate_skills_cache = None
    _pet_trait_cache = None
