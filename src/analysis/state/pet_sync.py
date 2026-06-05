"""Pure helpers for side/slot ownership bookkeeping."""
from __future__ import annotations

from typing import Any, Dict, MutableMapping, MutableSet, Optional


def side_int(side_value: Any) -> Optional[int]:
    try:
        return int(side_value)
    except (TypeError, ValueError):
        return None


def side_is_player(
    side_value: Any,
    *,
    battle_side_pets: MutableMapping[int, Dict[str, Any]],
    player_slots: MutableSet[int],
    opponent_slots: MutableSet[int],
    my_pets: list[Dict[str, Any]],
) -> bool:
    """Resolve whether a side value belongs to the player with known mappings first."""
    if side_value is None:
        return False
    if isinstance(side_value, str):
        return side_value == "我方"
    value = int(side_value)
    pet = battle_side_pets.get(value)
    if pet is not None:
        return pet in my_pets
    if value in opponent_slots:
        return False
    if value in player_slots:
        return True
    return 1 <= value <= 6


def bind_side_slot(
    side_value: Any,
    pet: Optional[Dict[str, Any]],
    *,
    battle_side_pets: MutableMapping[int, Dict[str, Any]],
    player_slots: MutableSet[int],
    opponent_slots: MutableSet[int],
    is_mine: bool,
) -> None:
    side_num = side_int(side_value)
    if side_num is None or pet is None:
        return
    battle_side_pets[side_num] = pet
    if is_mine:
        player_slots.add(side_num)
        opponent_slots.discard(side_num)
    else:
        opponent_slots.add(side_num)
        player_slots.discard(side_num)
