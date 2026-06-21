"""BattleStateTracker 的纯辅助函数。

这些函数不持有 tracker 实例状态，集中管理初始状态结构和小型字典操作，
避免状态机主类同时承担结构声明和工具函数职责。
"""
from __future__ import annotations

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
        "terminal_pending": False,
        "role_resources": {},
        "battle_resource": {},
        "role_resource_events": [],
    }


def clone_state_with_effective_speed(state: Dict[str, Any]) -> Dict[str, Any]:
    """兼容旧导入名；状态快照投影实现位于 state.snapshot。"""
    from src.analysis.state.snapshot import build_state_snapshot
    return build_state_snapshot(state)


def compute_effective_speed(pet: Dict[str, Any]) -> Optional[int]:
    """兼容旧导入名；速度快照派生实现位于 state.snapshot。"""
    from src.analysis.state.snapshot import compute_effective_speed as _compute_effective_speed
    return _compute_effective_speed(pet)


def append_bounded(items: List[Dict[str, Any]], item: Dict[str, Any], limit: int) -> None:
    items.append(item)
    if len(items) > limit:
        del items[:len(items) - limit]


def pick_keys(entry: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {key: entry[key] for key in keys if key in entry and entry[key] is not None}
