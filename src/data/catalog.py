"""游戏静态数据 catalog 兼容门面。

本模块保留历史导入路径；具体职责拆到：
- ``catalog_files.py``：数据目录、JSON 文件路径和安全读取。
- ``catalog_bundle.py``：基础 bundle/name-map 缓存。
- ``catalog_lookup.py``：ID 规范化、元数据查询和名称查询。
"""
from __future__ import annotations

from src.data.catalog_bundle import (
    _int_keyed_meta,
    _load_all_maps,
    _load_json_bundle,
    _name_map_from_meta,
    get_bundle,
    get_maps,
    invalidate_catalog_cache,
)
from src.data.catalog_files import (
    DATA_DIR,
    PROJECT_ROOT,
    _JSON_PATHS,
    _read_json_dict,
    _safe_int,
)
from src.data.catalog_lookup import (
    _MetaNormalizer,
    _get_bundle_meta,
    _get_name_from_meta_or_map,
    _normalize_lookup_value,
    _normalize_skill_id,
    get_attr_meta,
    get_attr_name,
    get_buff_meta,
    get_buffbase_meta,
    get_opcode_pb_meta,
    get_pb_message_meta,
    get_pet_meta,
    get_pet_name,
    get_skill_meta,
    get_skill_name,
)

__all__ = [
    "DATA_DIR",
    "PROJECT_ROOT",
    "_JSON_PATHS",
    "_MetaNormalizer",
    "_get_bundle_meta",
    "_get_name_from_meta_or_map",
    "_int_keyed_meta",
    "_load_all_maps",
    "_load_json_bundle",
    "_name_map_from_meta",
    "_normalize_lookup_value",
    "_normalize_skill_id",
    "_read_json_dict",
    "_safe_int",
    "get_attr_meta",
    "get_attr_name",
    "get_buff_meta",
    "get_buffbase_meta",
    "get_bundle",
    "get_maps",
    "get_opcode_pb_meta",
    "get_pb_message_meta",
    "get_pet_meta",
    "get_pet_name",
    "get_skill_meta",
    "get_skill_name",
    "invalidate_catalog_cache",
]
