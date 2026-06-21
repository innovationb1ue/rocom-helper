"""事件格式化共享类型和侧边解析工具。"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Optional


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
    if isinstance(side, str) and side in {"系统", "我方", "敌方"}:
        return side
    value = _as_int(side)
    if value is None:
        return str(side)
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
    value = _as_int(side_value)
    if value is None:
        return False
    return 1 <= value <= 6


def resolve_pet_name(slot_or_id: Any, is_my_side: bool, state: Dict[str, Any]) -> str:
    pet_list = state.get("my_pets", []) if is_my_side else state.get("opp_pets", [])
    for pet in pet_list:
        if _pet_matches_identifier(pet, slot_or_id):
            return pet.get("name", str(slot_or_id))
    return str(slot_or_id)


def resolve_pet_display_name(
    side_value: Any,
    state: Dict[str, Any],
    *,
    pet_id: Any = None,
) -> str:
    """Resolve the most specific display name available for a combat target."""
    fallback = side_label(side_value)
    ids = [value for value in (pet_id, side_value) if value is not None]
    pet_lists = _candidate_pet_lists(side_value, state)
    for identifier in ids:
        for pet in _iter_pets(pet_lists):
            if _pet_matches_identifier(pet, identifier):
                return pet.get("name") or fallback
    return fallback


def _candidate_pet_lists(side_value: Any, state: Dict[str, Any]) -> Iterable[list]:
    if is_mine(side_value):
        return [state.get("my_pets", []), state.get("opp_pets", [])]
    if side_label(side_value) == "敌方":
        return [state.get("opp_pets", []), state.get("my_pets", [])]
    return [state.get("my_pets", []), state.get("opp_pets", [])]


def _iter_pets(pet_lists: Iterable[list]) -> Iterable[Dict[str, Any]]:
    for pet_list in pet_lists:
        for pet in pet_list or []:
            yield pet


def _pet_matches_identifier(pet: Dict[str, Any], identifier: Any) -> bool:
    return any(
        _same_identifier(pet.get(key), identifier)
        for key in ("slot", "pet_id", "pending_supply_side")
    )


def _same_identifier(left: Any, right: Any) -> bool:
    if left == right:
        return True
    left_int = _as_int(left)
    right_int = _as_int(right)
    return left_int is not None and left_int == right_int


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
