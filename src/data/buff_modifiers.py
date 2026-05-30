"Buff、速度和伤害减免修正查询。"
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Set

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

# buff_id → [child_buff_id, ...] cached lookup. Repeated child ids are kept:
# 光加魔攻 -> 20010020 x4 means +40% magic attack, not +10%.
_buff_child_cache: Optional[Dict[int, List[int]]] = None

# 折射本体是按系别选择子效果的 selector，不能在没有协议上下文时展开所有子效果。
_TOP_LEVEL_SELECTOR_BUFF_IDS = {20890020}

_POWER_FLAT_BUFF_IDS = {
    20230440: 10,  # 通用威力+10
}
_HIT_FLAT_BUFF_IDS = {
    20450050: 1,   # 通用连击次数+1
    20450090: -1,  # 通用连击次数-1
}
_GENERIC_DAMAGE_MODIFIER_BUFF_IDS = set(_POWER_FLAT_BUFF_IDS) | set(_HIT_FLAT_BUFF_IDS)

# 折射派生的“系别效果”只对同属性技能生效；普通=0, 翼=9。
_BUFF_ELEMENT_SCOPES = {
    20640140: 0,  # 普通
    20171870: 0,  # 普通加威力
    20640260: 9,  # 翼
    20172000: 9,  # 翼加连击
}


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


def _build_buff_child_table() -> Dict[int, List[int]]:
    """构建 buff_id → 子 buff ids，用于显式派生 buff 的递归展开。"""
    bundle = get_bundle()
    buff_meta = bundle.get("buff_meta", {})
    buffbase_meta = bundle.get("buffbase_meta", {})
    known_buff_ids = set(buff_meta.keys())

    table: Dict[int, List[int]] = {}
    for buff_id, buff_entry in buff_meta.items():
        children: List[int] = []
        for bb_id in buff_entry.get("buff_base_ids") or []:
            bb = buffbase_meta.get(bb_id)
            if not bb:
                continue
            for param in bb.get("buffbase_param", []) or []:
                for raw in param.get("params", []) or []:
                    try:
                        child_id = int(raw)
                    except (TypeError, ValueError):
                        continue
                    if child_id != buff_id and child_id in known_buff_ids:
                        children.append(child_id)
        if children:
            table[buff_id] = children
    return table


def _ensure_buff_tables() -> None:
    global _buff_stat_cache, _buff_child_cache
    if _buff_stat_cache is None:
        _buff_stat_cache = _build_buff_stat_table()
    if _buff_child_cache is None:
        _buff_child_cache = _build_buff_child_table()


def _merge_modifiers(target: Dict[str, float], source: Dict[str, float], factor: float = 1.0) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0.0) + value * factor


def _resolve_buff_modifiers(
    buff_id: int,
    *,
    include_children: bool,
    seen: Optional[Set[int]] = None,
) -> Dict[str, float]:
    """解析单个 buff 的属性修正。

    ``include_children`` 只在子效果已经明确时打开；折射本体这类 selector
    不能直接展开，否则会把所有系别效果同时加上。
    """
    _ensure_buff_tables()
    assert _buff_stat_cache is not None
    assert _buff_child_cache is not None

    seen = set(seen or set())
    if buff_id in seen:
        return {}
    seen.add(buff_id)

    result: Dict[str, float] = dict(_buff_stat_cache.get(buff_id) or {})
    if not include_children:
        return result

    for child_id in _buff_child_cache.get(buff_id, []):
        _merge_modifiers(
            result,
            _resolve_buff_modifiers(child_id, include_children=True, seen=set(seen)),
        )
    return result


def _collect_buff_ids(
    buff_id: int,
    *,
    include_children: bool,
    seen: Optional[Set[int]] = None,
) -> List[int]:
    _ensure_buff_tables()
    assert _buff_child_cache is not None

    seen = set(seen or set())
    if buff_id in seen:
        return []
    seen.add(buff_id)

    ids = [buff_id]
    if not include_children:
        return ids
    for child_id in _buff_child_cache.get(buff_id, []):
        ids.extend(_collect_buff_ids(child_id, include_children=True, seen=set(seen)))
    return ids


def _collect_effective_buff_ids(
    buff_id: int,
    *,
    include_children: bool,
    root_id: Optional[int] = None,
    seen: Optional[Set[int]] = None,
) -> List[tuple[int, int]]:
    _ensure_buff_tables()
    assert _buff_child_cache is not None

    seen = set(seen or set())
    if buff_id in seen:
        return []
    seen.add(buff_id)
    root_id = root_id if root_id is not None else buff_id

    ids = [(buff_id, root_id)]
    if not include_children:
        return ids
    for child_id in _buff_child_cache.get(buff_id, []):
        ids.extend(
            _collect_effective_buff_ids(
                child_id,
                include_children=True,
                root_id=root_id,
                seen=set(seen),
            )
        )
    return ids


def _coerce_buff_id(value: Any) -> Optional[int]:
    if isinstance(value, dict):
        value = value.get("id") or value.get("buff_id") or value.get("effect_id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _buff_stage(buff: Dict[str, Any]) -> int:
    try:
        return max(1, int(buff.get("stage", 1) or 1))
    except (TypeError, ValueError):
        return 1


def _iter_derived_buffs(buff: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for item in buff.get("derived_buffs") or []:
        if isinstance(item, dict):
            yield item
        else:
            yield {"id": item}


def get_buff_derived_stat_modifiers(buff_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """只计算 buff 字典中显式记录的 derived_buffs 属性修正。"""
    result: Dict[str, float] = {}
    for buff in buff_list:
        for child in _iter_derived_buffs(buff):
            child_id = _coerce_buff_id(child)
            if child_id is None:
                continue
            child_mods = _resolve_buff_modifiers(child_id, include_children=True)
            _merge_modifiers(result, child_mods, _buff_stage(child))
    return result


def _iter_effective_buff_ids(buff_list: List[Dict[str, Any]]) -> Iterable[tuple[int, int, Dict[str, Any]]]:
    for buff in buff_list:
        buff_id = _coerce_buff_id(buff)
        if buff_id is None:
            continue
        include_children = buff_id not in _TOP_LEVEL_SELECTOR_BUFF_IDS
        for item_id, root_id in _collect_effective_buff_ids(buff_id, include_children=include_children):
            yield item_id, root_id, buff
        for child in _iter_derived_buffs(buff):
            child_id = _coerce_buff_id(child)
            if child_id is None:
                continue
            for item_id, root_id in _collect_effective_buff_ids(child_id, include_children=True):
                yield item_id, root_id, child


def _damage_modifier_applies(
    root_id: int,
    source_buff: Dict[str, Any],
    *,
    skill_element: Optional[int],
    skill_name: Optional[str],
) -> bool:
    source_skill = source_buff.get("source_skill")
    if source_skill and skill_name and source_skill != skill_name:
        return False
    scoped_element = _BUFF_ELEMENT_SCOPES.get(root_id)
    if scoped_element is not None and skill_element is not None:
        return scoped_element == skill_element
    if skill_element is not None and root_id in _GENERIC_DAMAGE_MODIFIER_BUFF_IDS and not source_skill:
        return False
    return True


def get_buff_power_modifiers(
    buff_list: List[Dict[str, Any]],
    *,
    skill_element: Optional[int] = None,
    skill_name: Optional[str] = None,
) -> Dict[str, float]:
    """解析 buff 派生的技能威力修正。当前返回 flat 加值。"""
    flat = 0.0
    sources: List[int] = []
    for buff_id, root_id, source_buff in _iter_effective_buff_ids(buff_list):
        if not _damage_modifier_applies(
            root_id,
            source_buff,
            skill_element=skill_element,
            skill_name=skill_name,
        ):
            continue
        value = _POWER_FLAT_BUFF_IDS.get(buff_id)
        if value is None:
            continue
        flat += value
        sources.append(buff_id)
    return {"flat": flat, "sources": sources} if flat else {}


def get_buff_hit_count_modifiers(
    buff_list: List[Dict[str, Any]],
    *,
    skill_element: Optional[int] = None,
    skill_name: Optional[str] = None,
) -> Dict[str, float]:
    """解析 buff 派生的连击次数修正。当前返回 flat 加值。"""
    flat = 0.0
    sources: List[int] = []
    for buff_id, root_id, source_buff in _iter_effective_buff_ids(buff_list):
        if not _damage_modifier_applies(
            root_id,
            source_buff,
            skill_element=skill_element,
            skill_name=skill_name,
        ):
            continue
        value = _HIT_FLAT_BUFF_IDS.get(buff_id)
        if value is None:
            continue
        flat += value
        sources.append(buff_id)
    return {"flat": flat, "sources": sources} if flat else {}


def get_buff_stat_modifiers(buff_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """从 buff 列表解析属性修正，返回 {"atk_up": 0.2, "spa_down": 0.1, ...}。"""
    _ensure_buff_tables()

    result: Dict[str, float] = {}
    for buff in buff_list:
        buff_id = _coerce_buff_id(buff)
        if buff_id is None:
            continue
        include_children = buff_id not in _TOP_LEVEL_SELECTOR_BUFF_IDS
        mods = _resolve_buff_modifiers(buff_id, include_children=include_children)
        if mods:
            _merge_modifiers(result, mods, _buff_stage(buff))
        derived_mods = get_buff_derived_stat_modifiers([buff])
        if derived_mods:
            _merge_modifiers(result, derived_mods)
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
    derived_modifiers = get_buff_derived_stat_modifiers([enriched])
    modifiers = get_buff_stat_modifiers([enriched])
    if derived_modifiers:
        enriched["derived_modifier_summary"] = format_buff_modifier_summary(derived_modifiers)
    else:
        enriched.pop("derived_modifier_summary", None)
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
    global _buff_stat_cache, _buff_child_cache, _speed_buff_cache, _buff_dmg_reduce_cache
    _buff_stat_cache = None
    _buff_child_cache = None
    _speed_buff_cache = None
    _buff_dmg_reduce_cache = None
