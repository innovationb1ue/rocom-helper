"""事件格式化共享类型和侧边解析工具。"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class FormattedEvent:
    kind: str
    round: int
    summary: str
    detail: Dict[str, Any]
    icon: str
    color: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def side_label(side: Optional[Any]) -> str:
    if side is None:
        return "?"
    value = int(side) if not isinstance(side, int) else side
    if value == 0:
        return "系统"
    if 1 <= value <= 6:
        return "我方"
    if value >= 401:
        return "敌方"
    return f"side={value}"


def is_mine(side_value: Any) -> bool:
    if side_value is None:
        return False
    if isinstance(side_value, str):
        return side_value == "我方"
    value = int(side_value)
    return 1 <= value <= 6


def resolve_pet_name(slot_or_id: Any, is_my_side: bool, state: Dict[str, Any]) -> str:
    pet_list = state.get("my_pets", []) if is_my_side else state.get("opp_pets", [])
    for pet in pet_list:
        if pet.get("slot") == slot_or_id or pet.get("pet_id") == slot_or_id:
            return pet.get("name", str(slot_or_id))
    return str(slot_or_id)
