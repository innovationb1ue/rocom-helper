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
    "innate_skills": DATA_DIR / "innate_skills.json",
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
    global _json_cache, _maps_cache, _innate_skills_cache
    with _lock:
        _json_cache = None
        _maps_cache = None
        _innate_skills_cache = None


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
    path = _JSON_PATHS["wiki_pets"]
    if not path.exists():
        return _pet_trait_cache
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return _pet_trait_cache
    if not isinstance(data, list):
        return _pet_trait_cache
    skill_map = get_bundle().get("skill_meta", {})
    for pet in data:
        ability = pet.get("ability")
        if not ability or not isinstance(ability, str):
            continue
        name = pet.get("name", "")
        if not name or name in _pet_trait_cache:
            continue
        trait_info: Dict[str, str] = {"name": ability, "description": ""}
        # Find skill_id and description from skill_map
        for sid, meta in skill_map.items():
            if meta.get("name") == ability:
                trait_info["description"] = meta.get("desc", "")
                break
        _pet_trait_cache[name] = trait_info
    return _pet_trait_cache


def get_pet_innate_trait(pet_name: str) -> Optional[Dict[str, str]]:
    """按精灵名查找先天特性（来自 wiki_pets.json）。"""
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


# ── Buff 属性修正查询 ──────────────────────────────────────────────

# attr_map ID → stat modifier key
_ATTR_TO_STAT_KEY = {
    29: "atk_up", 30: "spa_up", 31: "def_up", 32: "spd_up",
    33: "atk_down", 34: "spa_down", 35: "def_down", 36: "spd_down",
}

# buff_id → {"atk_up": 0.2, "atk_down": 0.0, ...} cached lookup
_buff_stat_cache: Optional[Dict[int, Dict[str, float]]] = None


def _build_buff_stat_table() -> Dict[int, Dict[str, float]]:
    """从 buff_map.json → buffbase_map.json 构建 buff_id → 属性修正映射。"""
    bundle = get_bundle()
    buff_meta = bundle.get("buff_meta", {})
    buffbase_meta = bundle.get("buffbase_meta", {})

    table: Dict[int, Dict[str, float]] = {}
    for buff_id, buff_entry in buff_meta.items():
        base_ids = buff_entry.get("buff_base_ids") or []
        if not base_ids:
            continue
        mods: Dict[str, float] = {}
        for bb_id in base_ids:
            bb = buffbase_meta.get(bb_id)
            if not bb:
                continue
            params_list = bb.get("buffbase_param", [])
            if len(params_list) < 3:
                continue
            attr_id = None
            value = None
            try:
                attr_id = params_list[0].get("params", [None])[0]
                value = params_list[2].get("params", [None])[0]
            except (IndexError, AttributeError):
                continue
            if attr_id is None or value is None:
                continue
            stat_key = _ATTR_TO_STAT_KEY.get(attr_id)
            if stat_key:
                mods[stat_key] = mods.get(stat_key, 0.0) + value / 1000.0
        if mods:
            table[buff_id] = mods
    return table


def get_buff_stat_modifiers(buff_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """从 buff 列表解析属性修正，返回 {"atk_up": 0.2, "spa_down": 0.1, ...}。"""
    global _buff_stat_cache
    if _buff_stat_cache is None:
        _buff_stat_cache = _build_buff_stat_table()

    result: Dict[str, float] = {}
    for buff in buff_list:
        buff_id = buff.get("id")
        if buff_id is None:
            continue
        mods = _buff_stat_cache.get(buff_id)
        if mods:
            for key, val in mods.items():
                result[key] = result.get(key, 0.0) + val
    return result


# ── 天气修正查询 ──────────────────────────────────────────────

# NRC_AI: rain → 水系技能 x1.5, sandstorm/snow → 无伤害修正
# skill_element 使用 type chart ID (water=2), 而非 SDT 值 (water=5)
_WATER_TYPE_ID = 2  # type_chart.json 中水的 ID


def get_weather_damage_mult(weather: Optional[Dict[str, Any]], skill_element: int) -> float:
    """根据天气和技能属性（type chart ID）返回伤害修正倍率。"""
    if not weather:
        return 1.0
    name = weather.get("name") or ""
    is_rain = "雨" in name
    if is_rain and skill_element == _WATER_TYPE_ID:
        return 1.5
    return 1.0
