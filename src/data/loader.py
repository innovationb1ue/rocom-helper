"""游戏数据加载器：从本地 JSON 文件加载精灵、技能、属性等游戏数据。"""
from __future__ import annotations
import json
import logging
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "game"

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
    "wiki_pets": DATA_DIR / "wiki_pets.json",
    "wiki_skills": DATA_DIR / "wiki_skills.json",
}

_json_cache: Optional[Dict[str, Any]] = None
_maps_cache: Optional[Dict[str, Dict[int, str]]] = None
_lock = threading.RLock()


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


_MetaNormalizer = Callable[[Optional[int]], Optional[int]]


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


def _normalize_lookup_value(value: Optional[int], *, normalizer: Optional[_MetaNormalizer] = None) -> Optional[int]:
    if value is None:
        return None
    normalized = normalizer(value) if normalizer else value
    if normalized is None:
        return None
    return int(normalized)


def _get_bundle_meta(*bundle_keys: str, value: Optional[int], normalizer: Optional[_MetaNormalizer] = None) -> Optional[Dict[str, Any]]:
    lookup_key = _normalize_lookup_value(value, normalizer=normalizer)
    if lookup_key is None:
        return None
    bundle = get_bundle()
    for bundle_key in bundle_keys:
        entry = bundle.get(bundle_key, {}).get(lookup_key)
        if isinstance(entry, dict):
            return entry
    return None


def _get_name_from_meta_or_map(*bundle_keys: str, value: Optional[int], map_name: Optional[str] = None, normalizer: Optional[_MetaNormalizer] = None) -> Optional[str]:
    meta = _get_bundle_meta(*bundle_keys, value=value, normalizer=normalizer)
    if meta and isinstance(meta.get("name"), str):
        return meta["name"]
    if map_name is None:
        return None
    lookup_key = _normalize_lookup_value(value, normalizer=normalizer)
    if lookup_key is None:
        return None
    return get_maps()[map_name].get(lookup_key)


def get_attr_meta(attr_id: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("attr_meta", value=attr_id)

def get_attr_name(attr_id: Optional[int]) -> Optional[str]:
    return _get_name_from_meta_or_map("attr_meta", value=attr_id, map_name="attr")

def get_skill_meta(skill_id: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("skill_meta", value=skill_id, normalizer=_normalize_skill_id)

def get_skill_name(skill_id: Optional[int]) -> Optional[str]:
    return _get_name_from_meta_or_map("skill_meta", value=skill_id, map_name="skill", normalizer=_normalize_skill_id)

def get_buff_meta(buff_id: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("buff_meta", value=buff_id)

def get_buffbase_meta(buffbase_id: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("buffbase_meta", value=buffbase_id)

def get_pet_meta(pet_id: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("pet_meta", "monster_meta", value=pet_id)

def get_pet_name(pet_id: Optional[int]) -> Optional[str]:
    return _get_name_from_meta_or_map("pet_meta", "monster_meta", value=pet_id, map_name="pet")

def get_pet_skill_meta(base_id: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("pet_skill_meta", value=base_id)

def get_opcode_pb_meta(opcode: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("opcode_pb_meta", value=opcode)

def get_pb_message_meta(name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    value = get_bundle().get("pb_message_meta", {}).get(name)
    return value if isinstance(value, dict) else None

def invalidate_cache() -> None:
    """热重载 / 测试时调用，使下次查询重新读取数据文件。"""
    global _json_cache, _maps_cache
    with _lock:
        _json_cache = None
        _maps_cache = None


# ── Wiki 数据查询 ──────────────────────────────────────────────

def _load_wiki_pets() -> Dict[str, Any]:
    """加载 wiki_pets.json，按 name 索引。"""
    path = _JSON_PATHS["wiki_pets"]
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, list):
        return {r.get("name", ""): r for r in data if r.get("name")}
    return {}


def _load_wiki_skills() -> Dict[str, Any]:
    """加载 wiki_skills.json，按 name 索引。"""
    path = _JSON_PATHS["wiki_skills"]
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, list):
        return {r.get("name", ""): r for r in data if r.get("name")}
    return {}


_wiki_pets_cache: Optional[Dict[str, Any]] = None
_wiki_skills_cache: Optional[Dict[str, Any]] = None


def get_wiki_pet(name: str) -> Optional[Dict[str, Any]]:
    """按名称查找 wiki 精灵数据。"""
    global _wiki_pets_cache
    if _wiki_pets_cache is None:
        _wiki_pets_cache = _load_wiki_pets()
    return _wiki_pets_cache.get(name)


def get_wiki_skill(name: str) -> Optional[Dict[str, Any]]:
    """按名称查找 wiki 技能数据。"""
    global _wiki_skills_cache
    if _wiki_skills_cache is None:
        _wiki_skills_cache = _load_wiki_skills()
    return _wiki_skills_cache.get(name)


def get_wiki_pet_types(name: str) -> List[int]:
    """获取精灵的属性 ID 列表（优先 wiki，回退游戏数据）。"""
    wp = get_wiki_pet(name)
    if wp and wp.get("types"):
        return wp["types"]
    return []


def get_wiki_pet_stats(name: str) -> Dict[str, int]:
    """获取精灵种族值（优先 wiki）。"""
    wp = get_wiki_pet(name)
    if wp and wp.get("stats"):
        return wp["stats"]
    return {}


def get_wiki_pet_skills(name: str) -> List[str]:
    """获取精灵的本系技能名称列表。"""
    wp = get_wiki_pet(name)
    if wp and wp.get("skills"):
        return wp["skills"]
    return []
