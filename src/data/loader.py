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
    if value is None:
        return None
    bundle = get_bundle()
    # Try raw value first — avoids false normalization of legitimate IDs
    for bundle_key in bundle_keys:
        entry = bundle.get(bundle_key, {}).get(value)
        if isinstance(entry, dict):
            return entry
    # Try normalized value as fallback (protocol may send id*100)
    if normalizer:
        normalized = normalizer(value)
        if normalized is not None and normalized != value:
            for bundle_key in bundle_keys:
                entry = bundle.get(bundle_key, {}).get(normalized)
                if isinstance(entry, dict):
                    return entry
    return None


def _get_name_from_meta_or_map(*bundle_keys: str, value: Optional[int], map_name: Optional[str] = None, normalizer: Optional[_MetaNormalizer] = None) -> Optional[str]:
    meta = _get_bundle_meta(*bundle_keys, value=value, normalizer=normalizer)
    if meta and isinstance(meta.get("name"), str):
        return meta["name"]
    if map_name is None:
        return None
    maps = get_maps()
    # Try raw value first
    name = maps[map_name].get(value)
    if name:
        return name
    # Try normalized fallback
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

def get_opcode_pb_meta(opcode: Optional[int]) -> Optional[Dict[str, Any]]:
    return _get_bundle_meta("opcode_pb_meta", value=opcode)

def get_pb_message_meta(name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    value = get_bundle().get("pb_message_meta", {}).get(name)
    return value if isinstance(value, dict) else None

def invalidate_cache() -> None:
    """热重载 / 测试时调用，使下次查询重新读取数据文件。"""
    global _json_cache, _maps_cache, _innate_skills_cache, _buff_dmg_reduce_cache
    global _pet_species_cache, _pet_trait_cache, _name_to_base_id_cache
    global _nature_cache, _nature_by_name_cache
    global _evolution_cache, _evo_by_petbase_cache
    global _battle_config_cache, _weather_cache
    with _lock:
        _json_cache = None
        _maps_cache = None
        _innate_skills_cache = None
        _buff_dmg_reduce_cache = None
        _pet_species_cache = None
        _pet_trait_cache = None
        _name_to_base_id_cache = None
        _nature_cache = None
        _nature_by_name_cache = None
        _evolution_cache = None
        _evo_by_petbase_cache = None
        _battle_config_cache = None
        _weather_cache = None


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


# ── Buff 属性修正查询 ──────────────────────────────────────────────

# attr_map ID → stat modifier key
_ATTR_TO_STAT_KEY = {
    17: "atk_up", 18: "spa_up",
    29: "atk_up", 30: "spa_up", 31: "def_up", 32: "spd_up",
    33: "atk_down", 34: "spa_down", 35: "def_down", 36: "spd_down",
}

# 某些 attr_id 的值存储在 params[4] 而非 params[2]
_ATTR_USING_PARAM4 = {17, 18}

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
                raw_val = params_list[2].get("params", [None])[0]
                # 某些 attr_id（如 17/18）的值存储在 params[4]
                if (raw_val == 0 or raw_val is None) and attr_id in _ATTR_USING_PARAM4 and len(params_list) >= 5:
                    raw_val = params_list[4].get("params", [None])[0]
                value = raw_val
            except (IndexError, AttributeError):
                continue
            if attr_id is None or value is None:
                continue
            stat_key = _ATTR_TO_STAT_KEY.get(attr_id)
            if stat_key:
                mods[stat_key] = mods.get(stat_key, 0.0) + value / 10000.0
            else:
                logger.debug("Unmapped buff attr_id %s in buffbase %s (buff %s)", attr_id, bb_id, buff_id)
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
            stage = max(1, int(buff.get("stage", 1)))
            for key, val in mods.items():
                result[key] = result.get(key, 0.0) + val * stage
    return result


# ── Buff 速度修正查询 ──────────────────────────────────────────────

_SPEED_STAT_PARAM = 6  # buffbase params[0] = 6 表示速度
_speed_buff_cache: Optional[Dict[int, Dict[str, float]]] = None


def _build_speed_buff_table() -> Dict[int, Dict[str, float]]:
    """从 buff_map.json → buffbase_map.json 构建 buff_id → 速度修正映射。

    buffbase param 结构 (params 按 3 个一组):
      params[0] = 6 (速度属性标识)
      params[1] = 0 → 固定值修改, params[2] = ±N
      params[1] = 1 → 百分比修改, params[2] = N (N/10000)
    """
    bundle = get_bundle()
    buff_meta = bundle.get("buff_meta", {})
    buffbase_meta = bundle.get("buffbase_meta", {})

    table: Dict[int, Dict[str, float]] = {}
    for buff_id, buff_entry in buff_meta.items():
        base_ids = buff_entry.get("buff_base_ids") or []
        if not base_ids:
            continue
        flat = 0.0
        pct = 0.0
        for bb_id in base_ids:
            bb = buffbase_meta.get(bb_id)
            if not bb:
                continue
            params_list = bb.get("buffbase_param", [])
            # params 按 3 个一组解析: [stat_id, mode, value]
            for i in range(0, len(params_list) - 2, 3):
                try:
                    p0 = params_list[i].get("params", [None])[0]
                    p1 = params_list[i + 1].get("params", [None])[0]
                    p2 = params_list[i + 2].get("params", [None])[0]
                except (IndexError, AttributeError):
                    continue
                if p0 != _SPEED_STAT_PARAM or p2 is None:
                    continue
                if p1 == 0:
                    flat += p2
                elif p1 == 1:
                    pct += p2 / 10000.0
        if flat != 0 or pct != 0:
            table[buff_id] = {"flat": flat, "pct": pct}
    return table


def get_speed_buff_modifiers(buff_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """从 buff 列表计算速度修正，返回 {"flat_total": float, "pct_total": float}。

    stage 表示 buff 层数，效果乘以 stage。
    """
    global _speed_buff_cache
    if _speed_buff_cache is None:
        _speed_buff_cache = _build_speed_buff_table()

    flat_total = 0.0
    pct_total = 0.0
    for buff in buff_list:
        buff_id = buff.get("id")
        if buff_id is None:
            continue
        mods = _speed_buff_cache.get(buff_id)
        if not mods:
            continue
        stage = max(1, int(buff.get("stage", 1)))
        flat_total += mods.get("flat", 0.0) * stage
        pct_total += mods.get("pct", 0.0) * stage
    return {"flat_total": flat_total, "pct_total": pct_total}


# ── Buff 伤害减免查询 ──────────────────────────────────────────────

# buff_id → {"reduction": 0.8, "damage_types": [2, 3]} cached lookup
_buff_dmg_reduce_cache: Optional[Dict[int, Dict[str, Any]]] = None


def _build_buff_damage_reduction_table() -> Dict[int, Dict[str, Any]]:
    """从 buff_map.json → buffbase_map.json 构建 buff_id → 伤害减免映射。

    buffbase param 结构:
      params[1] = 伤害类型过滤 ([2]=物理, [3]=特殊, [2,3]=全部)
      params[4] = 减免值 (负数, /10000, 如 -8000 = 80% 减免)
    """
    bundle = get_bundle()
    buff_meta = bundle.get("buff_meta", {})
    buffbase_meta = bundle.get("buffbase_meta", {})

    table: Dict[int, Dict[str, Any]] = {}
    for buff_id, buff_entry in buff_meta.items():
        base_ids = buff_entry.get("buff_base_ids") or []
        if not base_ids:
            continue
        total_reduction = 0.0
        dmg_types: set = set()
        for bb_id in base_ids:
            bb = buffbase_meta.get(bb_id)
            if not bb:
                continue
            params_list = bb.get("buffbase_param", [])
            if len(params_list) < 5:
                continue
            try:
                type_filter = params_list[1].get("params", [])
                reduce_val = params_list[4].get("params", [0])[0]
            except (IndexError, AttributeError):
                continue
            if reduce_val >= 0:
                continue
            total_reduction += abs(reduce_val) / 10000.0
            dmg_types.update(type_filter)
        if total_reduction > 0:
            table[buff_id] = {
                "reduction": total_reduction,
                "damage_types": sorted(dmg_types),
            }
    return table


def get_buff_damage_reduction(
    buff_list: List[Dict[str, Any]], damage_type: int,
) -> float:
    """从 buff 列表计算总伤害减免比例，过滤指定伤害类型 (2=物理, 3=特殊)。

    返回 0.0~0.95 之间的减免比例。
    """
    global _buff_dmg_reduce_cache
    if _buff_dmg_reduce_cache is None:
        _buff_dmg_reduce_cache = _build_buff_damage_reduction_table()

    total = 0.0
    for buff in buff_list:
        buff_id = buff.get("id")
        if buff_id is None:
            continue
        info = _buff_dmg_reduce_cache.get(buff_id)
        if not info:
            continue
        if damage_type not in info["damage_types"]:
            continue
        stage = max(1, int(buff.get("stage", 1)))
        total += info["reduction"] * stage
    return min(0.95, total)


# ── 天气修正查询 ──────────────────────────────────────────────

# NRC_AI: rain → 水系技能 x1.5, sandstorm/snow → 无伤害修正
# skill_element 使用 type chart ID (water=2), 而非 SDT 值 (water=5)
_WATER_TYPE_ID = 2  # type_chart.json 中水的 ID


def get_weather_damage_mult(weather: Optional[Dict[str, Any]], skill_element: int) -> float:
    """根据天气和技能属性（type chart ID）返回伤害修正倍率。"""
    if not weather:
        return 1.0
    name = weather.get("name") or ""
    if not isinstance(name, str):
        name = ""
    is_rain = "雨" in name
    if is_rain and skill_element == _WATER_TYPE_ID:
        return 1.5
    return 1.0


# ── 热门技能预设 ──────────────────────────────────────────────

CONFIG_DIR = PROJECT_ROOT / "data" / "config"
_POPULAR_SKILLS_PATH = CONFIG_DIR / "popular_skills.json"
_popular_skills_cache: Optional[Dict[str, Any]] = None


def _load_popular_skills() -> Dict[str, Any]:
    """加载 popular_skills.json，返回完整配置。"""
    global _popular_skills_cache
    if _popular_skills_cache is not None:
        return _popular_skills_cache
    path = _POPULAR_SKILLS_PATH
    if not path.exists():
        _popular_skills_cache = {"version": 1, "presets": {}}
        return _popular_skills_cache
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        _popular_skills_cache = {"version": 1, "presets": {}}
        return _popular_skills_cache
    _popular_skills_cache = data if isinstance(data, dict) else {"version": 1, "presets": {}}
    return _popular_skills_cache


def get_popular_skills(base_id: int) -> Optional[Dict[str, Any]]:
    """获取某精灵的热门技能预设。返回 {"name": ..., "skills": [...], "note": ...} 或 None。"""
    data = _load_popular_skills()
    presets = data.get("presets", {})
    return presets.get(str(base_id))


def get_all_popular_skills() -> Dict[str, Any]:
    """获取全部热门技能预设。"""
    return _load_popular_skills()


def save_popular_skills(base_id: int, name: str, skills: List[int], note: str = "") -> None:
    """保存某精灵的热门技能预设。"""
    data = _load_popular_skills()
    presets = data.setdefault("presets", {})
    presets[str(base_id)] = {"name": name, "skills": skills, "note": note}
    _save_popular_skills_file(data)


def delete_popular_skills(base_id: int) -> bool:
    """删除某精灵的热门技能预设。返回是否存在。"""
    data = _load_popular_skills()
    presets = data.get("presets", {})
    key = str(base_id)
    if key in presets:
        del presets[key]
        _save_popular_skills_file(data)
        return True
    return False


def _save_popular_skills_file(data: Dict[str, Any]) -> None:
    """将热门技能配置写入文件。"""
    global _popular_skills_cache
    _POPULAR_SKILLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _POPULAR_SKILLS_PATH.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    _popular_skills_cache = data


# ── BinData 物种数据查询 (pet_species.json) ──────────────────

_pet_species_cache: Optional[Dict[str, Any]] = None


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


# ── name → base_id 适配层 ──────────────────────────────────

_name_to_base_id_cache: Optional[Dict[str, int]] = None


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
            # 同名取第一个（通常是原始形态）
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


# ── 性格数据查询 (nature_map.json) ──────────────────────────

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
        for k, v in _load_nature_map().items():
            n = v.get("name", "")
            if n:
                _nature_by_name_cache[n] = v
    return _nature_by_name_cache.get(name)


def get_nature_stat_modifiers(nature_id: Optional[int]) -> Dict[str, float]:
    """获取性格的属性修正，返回 {"atk": 0.1, "spa": -0.1, ...} 或空 dict。

    proportion 单位: 1000 = +10%, -1000 = -10%。
    """
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


# ── 进化链数据查询 (evolution_map.json) ─────────────────────

_evolution_cache: Optional[Dict[str, Any]] = None
_evo_by_petbase_cache: Optional[Dict[int, str]] = None


def _load_evolution_map() -> Dict[str, Any]:
    global _evolution_cache
    if _evolution_cache is not None:
        return _evolution_cache
    path = DATA_DIR / "evolution_map.json"
    _evolution_cache = _read_json_dict(path)
    return _evolution_cache


def _build_evo_petbase_index() -> Dict[int, str]:
    """构建 petbase_id → evolution_id 索引。"""
    global _evo_by_petbase_cache
    if _evo_by_petbase_cache is not None:
        return _evo_by_petbase_cache
    _evo_by_petbase_cache = {}
    em = _load_evolution_map()
    for evo_id, evo in em.items():
        chain = evo.get("evolution_chain", [])
        for stage in chain:
            pb_id = stage.get("petbase_id")
            if pb_id is not None:
                _evo_by_petbase_cache[int(pb_id)] = evo_id
    return _evo_by_petbase_cache


def get_evolution_chain(evolution_id: Optional[int] = None,
                        petbase_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """按进化链 ID 或 petbase_id 查找进化链。"""
    em = _load_evolution_map()
    if evolution_id is not None:
        return em.get(str(evolution_id))
    if petbase_id is not None:
        idx = _build_evo_petbase_index()
        evo_id = idx.get(petbase_id)
        if evo_id:
            return em.get(str(evo_id))
    return None


def get_evolution_pvp_mute_group(petbase_id: int) -> Optional[int]:
    """获取进化链的 PvP mute group（同进化链在 PvP 中视为同一只精灵）。"""
    chain = get_evolution_chain(petbase_id=petbase_id)
    if chain:
        return chain.get("pvp_mute_group")
    return None


# ── 战斗全局配置查询 (battle_config.json) ───────────────────

_battle_config_cache: Optional[Dict[str, Any]] = None


def _load_battle_config() -> Dict[str, Any]:
    global _battle_config_cache
    if _battle_config_cache is not None:
        return _battle_config_cache
    path = DATA_DIR / "battle_config.json"
    _battle_config_cache = _read_json_dict(path)
    return _battle_config_cache


def get_battle_config() -> Dict[str, Any]:
    """获取战斗全局配置（克制倍率、捕捉参数等）。"""
    return _load_battle_config()


def get_restraint_multipliers() -> Dict[str, float]:
    """获取克制伤害倍率。

    返回 {"single_super": 1.0, "double_super": 2.0, "single_resist": 0.5, "double_resist": 0.75}
    使用 BATTLE_GLOBAL_CONFIG 数据，单位为万分比（10000=1.0）。
    """
    cfg = _load_battle_config()
    result = {"single_super": 1.0, "double_super": 2.0, "single_resist": 0.5, "double_resist": 0.75}

    for key, config_key in [
        ("single_super", "restraint_percent"),
        ("double_super", "double_restraint_percent"),
        ("single_resist", "restrained_percent"),
        ("double_resist", "double_restrained_percent"),
    ]:
        entry = cfg.get(config_key, {})
        val = entry.get("value")
        if isinstance(val, (int, float)) and val > 0:
            result[key] = val / 10000.0

    return result


# ── 天气数据查询 (weather_map.json) ─────────────────────────

_weather_cache: Optional[Dict[str, Any]] = None


def _load_weather_map() -> Dict[str, Any]:
    global _weather_cache
    if _weather_cache is not None:
        return _weather_cache
    path = DATA_DIR / "weather_map.json"
    _weather_cache = _read_json_dict(path)
    return _weather_cache


def get_weather(weather_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """按 weather_id 查找天气数据。"""
    if weather_id is None:
        return None
    return _load_weather_map().get(str(weather_id))


def get_weather_by_name(name: str) -> Optional[Dict[str, Any]]:
    """按天气名称查找天气数据。"""
    for k, v in _load_weather_map().items():
        if v.get("name") == name:
            return v
    return None


# ── 增强现有函数 ──────────────────────────────────────────────

# 重写 get_weather_damage_mult 使用真实天气数据
def get_weather_damage_mult(weather: Optional[Dict[str, Any]], skill_element: int) -> float:
    """根据天气和技能属性返回伤害修正倍率。

    优先使用 weather_map.json 数据；回退到旧的基于名称的简单判断。
    """
    if not weather:
        return 1.0

    weather_id = weather.get("weather") or weather.get("id")
    wdata = get_weather(weather_id)
    if wdata:
        # TODO: 从 weather_buff 解析实际伤害倍率
        # 当前根据天气名称做简单判断
        wname = wdata.get("name", "")
        if "雨" in wname and skill_element == _WATER_TYPE_ID:
            return 1.5
        # 晴天 + 火系 (TODO: 需要确认火系 type chart ID)
        if "晴" in wname:
            _FIRE_TYPE_ID = 1
            if skill_element == _FIRE_TYPE_ID:
                return 1.5
        return 1.0

    # 回退到旧逻辑
    name = weather.get("name") or ""
    if not isinstance(name, str):
        name = ""
    is_rain = "雨" in name
    if is_rain and skill_element == _WATER_TYPE_ID:
        return 1.5
    return 1.0


# 增强 get_wiki_pet_types：优先从 pet_species 获取
def get_pet_types_from_species(base_id: Optional[int]) -> List[int]:
    """从 pet_species 获取属性 ID。"""
    types = get_pet_species_types(base_id)
    if types:
        return types
    return []
