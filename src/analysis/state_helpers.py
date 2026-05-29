"""BattleStateTracker 的纯辅助函数。

这些函数不持有 tracker 实例状态，集中管理初始状态结构、速度计算和
小型字典操作，避免状态机主类同时承担结构声明和工具函数职责。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional


def initial_battle_state() -> Dict[str, Any]:
    """构造 BattleStateTracker 的初始 dict 状态。

    返回新对象，保证 reset/new tracker 之间不会共享可变列表。
    """
    initial_weather = {"id": None, "name": None, "expire_round": None}
    return {
        "battle_id": None,
        "battle_mode": None,
        "round": 0,
        "max_round": 0,
        "weather": initial_weather,
        "field_context": {
            "weather_current": initial_weather,
            "weather_history": [],
            "global_events": [],
            "perform_groups": [],
            "sync_events": [],
            "item_sync_events": [],
            "damage_ledger": [],
        },
        "phase": "idle",
        "my_pets": [],
        "opp_pets": [],
        "my_active": None,
        "opp_active": None,
        "events": [],
        "result": None,
    }


def clone_state_with_effective_speed(state: Dict[str, Any]) -> Dict[str, Any]:
    """深拷贝状态并为所有精灵补充 effective_speed。"""
    snapshot = copy.deepcopy(state)
    for pet in snapshot.get("my_pets", []) + snapshot.get("opp_pets", []):
        pet["effective_speed"] = compute_effective_speed(pet)
    for key in ("my_active", "opp_active"):
        active = snapshot.get(key)
        if active:
            active["effective_speed"] = compute_effective_speed(active)
    return snapshot


def compute_effective_speed(pet: Dict[str, Any]) -> Optional[int]:
    """计算实际速度 = (基础速度 + 固定修正) * (1 + 百分比修正 + 属性等级修正)。"""
    base = pet.get("base_speed")
    if base is None:
        return None
    from src.data.loader import get_buff_stat_modifiers, get_speed_buff_modifiers
    speed_mods = get_speed_buff_modifiers(pet.get("buffs", []))
    stat_mods = get_buff_stat_modifiers(pet.get("buffs", []))
    pct = (
        speed_mods.get("pct_total", 0.0)
        + stat_mods.get("spd_up", 0.0)
        - stat_mods.get("spd_down", 0.0)
    )
    effective = (base + speed_mods.get("flat_total", 0)) * (1.0 + pct)
    return max(1, int(round(effective)))


def append_bounded(items: List[Dict[str, Any]], item: Dict[str, Any], limit: int) -> None:
    items.append(item)
    if len(items) > limit:
        del items[:len(items) - limit]


def pick_keys(entry: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {key: entry[key] for key in keys if key in entry and entry[key] is not None}
