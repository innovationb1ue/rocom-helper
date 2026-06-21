"""状态投影共享工具。"""
from __future__ import annotations

from typing import Any, Dict, Optional


def active_for_side(state: Dict[str, Any], side_value: Any) -> Optional[Dict[str, Any]]:
    """根据 side 值获取对应的活跃宠物字典。"""
    if side_value is None:
        return None
    is_mine = False
    if isinstance(side_value, str):
        is_mine = side_value == "我方"
    else:
        value = int(side_value)
        is_mine = 1 <= value <= 6
    key = "my_active" if is_mine else "opp_active"
    return state.get(key)

