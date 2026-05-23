"""Stable battle identity helpers for runtime pet dictionaries."""
from __future__ import annotations

from typing import Any, Dict, Optional


HIDDEN_OPPONENT_PET_ID = 20000000


def is_hidden_pet_id(pet_id: Any) -> bool:
    try:
        return int(pet_id) == HIDDEN_OPPONENT_PET_ID
    except (TypeError, ValueError):
        return False


def side_key(side: Any) -> str:
    if side in (1, "我方", "鎴戞柟"):
        return "my"
    try:
        value = int(side)
    except (TypeError, ValueError):
        return str(side or "unknown")
    if value >= 401:
        return "opp"
    if 1 <= value <= 6:
        return "my"
    return str(value)


def battle_uid(pet: Dict[str, Any], *, side: Any = None) -> Optional[str]:
    """Build an identity that stays unique when opponent pet_id is hidden."""
    pet_side = pet.get("side", side)
    prefix = side_key(pet_side)

    slot = pet.get("slot")
    if slot is not None:
        return f"{prefix}:slot:{slot}"

    base_conf_id = pet.get("base_conf_id")
    if base_conf_id is not None:
        return f"{prefix}:base:{base_conf_id}"

    pet_id = pet.get("pet_id")
    if pet_id is not None and not is_hidden_pet_id(pet_id):
        return f"{prefix}:pet:{pet_id}"

    return None


def refresh_battle_uid(pet: Dict[str, Any], *, side: Any = None) -> Optional[str]:
    uid = battle_uid(pet, side=side)
    if uid is not None:
        pet["battle_uid"] = uid
    else:
        pet.pop("battle_uid", None)
    return uid


def same_battle_pet(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    left_uid = left.get("battle_uid") or battle_uid(left)
    right_uid = right.get("battle_uid") or battle_uid(right)
    if left_uid and right_uid:
        return left_uid == right_uid

    left_slot = left.get("slot")
    right_slot = right.get("slot")
    if left_slot is not None and right_slot is not None:
        return side_key(left.get("side")) == side_key(right.get("side")) and left_slot == right_slot

    left_base = left.get("base_conf_id")
    right_base = right.get("base_conf_id")
    if left_base is not None and right_base is not None:
        return side_key(left.get("side")) == side_key(right.get("side")) and left_base == right_base

    left_id = left.get("pet_id")
    right_id = right.get("pet_id")
    if left_id is not None and right_id is not None and not is_hidden_pet_id(left_id):
        return left_id == right_id

    return False
