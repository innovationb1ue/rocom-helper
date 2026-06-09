"""游戏数据加载器兼容门面。

外部调用方仍从 ``src.data.loader`` 导入所有数据访问函数；具体实现按
catalog、buff、物种/配置等领域逐步拆入内部模块，避免单文件继续膨胀。
"""
from __future__ import annotations

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
from src.data.innate import (
    _load_innate_skills,
    _load_pet_traits,
    get_innate_skill,
    get_innate_skills_for_pet,
    get_pet_innate_trait,
    reset_innate_caches,
)
from src.data.pet_skills import get_pet_skill_meta
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
from src.data.wiki_compat import (
    get_wiki_pet,
    get_wiki_pet_stats,
    get_wiki_pet_types,
    get_wiki_skill,
)


def invalidate_cache() -> None:
    """热重载 / 测试时调用，使下次查询重新读取数据文件。"""
    invalidate_catalog_cache()
    reset_buff_modifier_caches()
    reset_popular_skill_cache()
    reset_species_config_caches()
    reset_innate_caches()
