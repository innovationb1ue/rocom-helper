"Buff、速度和伤害减免修正查询。"
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.data.catalog import get_bundle

logger = logging.getLogger(__name__)

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


_BUFF_MODIFIER_LABELS = {
    "atk_up": "物攻",
    "atk_down": "物攻",
    "spa_up": "魔攻",
    "spa_down": "魔攻",
    "def_up": "物防",
    "def_down": "物防",
    "spd_up": "魔防",
    "spd_down": "魔防",
}


def _format_modifier_pct(value: float) -> str:
    pct = value * 100
    if abs(pct - round(pct)) < 0.001:
        return str(int(round(pct)))
    return f"{pct:.1f}".rstrip("0").rstrip(".")


def format_buff_modifier_summary(modifiers: Dict[str, float]) -> List[str]:
    """将属性修正转成人类可读摘要，例如 ["魔攻 +10%"]。"""
    summary: List[str] = []
    for key in ("atk_up", "atk_down", "spa_up", "spa_down", "def_up", "def_down", "spd_up", "spd_down"):
        value = modifiers.get(key)
        if not value:
            continue
        label = _BUFF_MODIFIER_LABELS.get(key, key)
        sign = "+" if key.endswith("_up") else "-"
        summary.append(f"{label} {sign}{_format_modifier_pct(abs(value))}%")
    return summary


def enrich_buff_modifiers(buff: Dict[str, Any]) -> Dict[str, Any]:
    """为 buff 字典补充确定属性数值，保留原字段并只添加紧凑解释字段。"""
    enriched = dict(buff)
    modifiers = get_buff_stat_modifiers([enriched])
    if modifiers:
        enriched["modifiers"] = modifiers
        enriched["modifier_summary"] = format_buff_modifier_summary(modifiers)
    else:
        enriched.pop("modifiers", None)
        enriched.pop("modifier_summary", None)
    return enriched


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


def reset_buff_modifier_caches() -> None:
    global _buff_stat_cache, _speed_buff_cache, _buff_dmg_reduce_cache
    _buff_stat_cache = None
    _speed_buff_cache = None
    _buff_dmg_reduce_cache = None
