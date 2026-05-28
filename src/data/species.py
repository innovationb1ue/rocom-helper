"宠物物种、性格、进化链、战斗配置和天气数据。"
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.data.catalog import DATA_DIR, _read_json_dict, get_bundle

_WATER_TYPE_ID = 2  # type_chart.json 中水的 ID

# ── BinData 物种数据查询 (pet_species.json) (pet_species.json) ──────────────────

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


def reset_species_config_caches() -> None:
    global _pet_species_cache, _name_to_base_id_cache
    global _nature_cache, _nature_by_name_cache
    global _evolution_cache, _evo_by_petbase_cache
    global _battle_config_cache, _weather_cache
    _pet_species_cache = None
    _name_to_base_id_cache = None
    _nature_cache = None
    _nature_by_name_cache = None
    _evolution_cache = None
    _evo_by_petbase_cache = None
    _battle_config_cache = None
    _weather_cache = None
