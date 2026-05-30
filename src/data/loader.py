"""游戏数据加载器兼容门面。

外部调用方仍从 ``src.data.loader`` 导入所有数据访问函数；具体实现按
catalog、buff、物种/配置等领域逐步拆入内部模块，避免单文件继续膨胀。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.config import settings
from src.data.catalog import (
    DATA_DIR,
    PROJECT_ROOT,
    _JSON_PATHS,
    _get_bundle_meta,
    _get_name_from_meta_or_map,
    _int_keyed_meta,
    _normalize_lookup_value,
    _normalize_skill_id,
    _read_json_dict,
    _safe_int,
    get_attr_meta,
    get_attr_name,
    get_buff_meta,
    get_buffbase_meta,
    get_bundle,
    get_maps,
    get_opcode_pb_meta,
    get_pb_message_meta,
    get_pet_meta,
    get_pet_name,
    get_skill_meta,
    get_skill_name,
    invalidate_catalog_cache,
)

logger = logging.getLogger(__name__)

from src.data.buff_modifiers import (
    enrich_buff_modifiers,
    format_buff_modifier_summary,
    get_buff_derived_stat_modifiers,
    get_buff_damage_reduction,
    get_buff_hit_count_modifiers,
    get_buff_power_modifiers,
    get_buff_stat_modifiers,
    get_speed_buff_modifiers,
    reset_buff_modifier_caches,
)
from src.data.presets import (
    delete_popular_skills,
    get_all_popular_skills,
    get_popular_skills,
    reset_popular_skill_cache,
    save_popular_skills,
)
from src.data.species import (
    _load_pet_species,
    get_base_id_by_name,
    get_battle_config,
    get_evolution_chain,
    get_evolution_pvp_mute_group,
    get_nature,
    get_nature_by_name,
    get_nature_stat_modifiers,
    get_pet_implemented,
    get_pet_species,
    get_pet_species_stats,
    get_pet_species_types,
    get_pet_types_from_species,
    get_restraint_multipliers,
    get_species_by_name,
    get_weather,
    get_weather_by_name,
    get_weather_damage_mult,
    reset_species_config_caches,
)

def get_pet_skill_meta(base_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """按 base_id 查找宠物技能数据。

    leader/boss 形态有独立的 base_id 但共享基础形态的 level_skill_conf_id，
    此函数会自动 fallback。
    """
    if base_id is None:
        return None
    # 先直接查
    result = _get_bundle_meta("pet_skill_meta", value=base_id)
    if result is not None:
        return result
    # fallback: 查 pet_species 的 level_skill_conf_id
    sp = get_pet_species(base_id)
    if sp:
        lsc_id = sp.get("level_skill_conf_id")
        if lsc_id:
            return _get_bundle_meta("pet_skill_meta", value=lsc_id)
    return None

def invalidate_cache() -> None:
    """热重载 / 测试时调用，使下次查询重新读取数据文件。"""
    global _innate_skills_cache, _pet_trait_cache
    invalidate_catalog_cache()
    reset_buff_modifier_caches()
    reset_popular_skill_cache()
    reset_species_config_caches()
    _innate_skills_cache = None
    _pet_trait_cache = None


# ── 宠物数据查询（BinData 来源，替代旧 wiki 数据）──────────

def get_wiki_pet(name: str) -> Optional[Dict[str, Any]]:
    """按名称查找精灵物种数据（来自 pet_species.json）。"""
    return get_species_by_name(name)


def get_wiki_skill(name: str) -> Optional[Dict[str, Any]]:
    """按名称查找技能数据（来自 skill_map.json）。已弃用，仅保留向后兼容。"""
    # 无调用者（routes_teams.py 的技能路径是死代码）
    bundle = get_bundle()
    skill_meta = bundle.get("skill_meta", {})
    for sid, entry in skill_meta.items():
        if entry.get("name") == name:
            return entry
    return None


def get_wiki_pet_types(name: str) -> List[int]:
    """获取精灵的属性 ID 列表（来自 pet_species.json）。"""
    sp = get_species_by_name(name)
    if sp and sp.get("types"):
        return sp["types"]
    return []


def get_wiki_pet_stats(name: str) -> Dict[str, int]:
    """获取精灵种族值（来自 pet_species.json，key 为小写 hp/atk/spa/def/spd/spe）。"""
    sp = get_species_by_name(name)
    if sp and sp.get("stats"):
        return sp["stats"]
    return {}


# ── 先天技能数据查询 ──────────────────────────────────────────────

_innate_skills_cache: Optional[Dict[str, Any]] = None


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


# Cache: pet_name → {name, description}
_pet_trait_cache: Optional[Dict[str, Dict[str, str]]] = None


def _load_pet_traits() -> Dict[str, Dict[str, str]]:
    global _pet_trait_cache
    if _pet_trait_cache is not None:
        return _pet_trait_cache
    _pet_trait_cache = {}
    skill_map = get_bundle().get("skill_meta", {})
    species_map = _load_pet_species()
    for base_id_str, sp in species_map.items():
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
