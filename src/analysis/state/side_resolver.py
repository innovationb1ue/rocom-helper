"""Side, active-pet, and stable identity resolution helpers."""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.analysis.pet_identity import is_hidden_pet_id, same_battle_pet
from src.analysis.state.pet_sync import bind_side_slot, side_int, side_is_player


def pet_for_sync_id(tracker: Any, pet_id: Any) -> Optional[Dict[str, Any]]:
    if pet_id is None:
        return None
    side_num = tracker._side_int(pet_id)
    if side_num is not None and side_num in tracker._battle_side_pets:
        pet = tracker._battle_side_pets[side_num]
        active_key = "my_active" if tracker._is_mine(side_num) else "opp_active"
        active = tracker.state.get(active_key)
        if (
            pet.get("current_hp", 0) <= 0
            and active is not None
            and active.get("current_hp", 0) > 0
        ):
            tracker._bind_battle_side(side_num, active, is_mine=(active_key == "my_active"))
            return active
        return pet
    for pet in tracker.state["my_pets"] + tracker.state["opp_pets"]:
        if pet.get("pet_id") == pet_id or pet.get("slot") == pet_id:
            return pet
    if side_num is not None:
        return tracker._resolve_pet_for_side(side_num, bind_fallback=False)
    return None


def pet_name_by_slot(tracker: Any, slot: Any, is_mine: bool) -> Optional[str]:
    side_num = tracker._side_int(slot)
    if side_num is not None:
        pet = tracker._battle_side_pets.get(side_num)
        if pet is not None:
            return pet.get("name")
    pet_list = tracker.state["my_pets"] if is_mine else tracker.state["opp_pets"]
    for pet in pet_list:
        if pet.get("slot") == slot or pet.get("pet_id") == slot:
            return pet.get("name")
    return None


def stable_pet_matches(pet: Dict[str, Any], wrapper: Dict[str, Any]) -> bool:
    w_pid = wrapper.get("pet_id") or wrapper.get("pet_gid")
    p_pid = pet.get("pet_id")
    w_pet = {
        "pet_id": w_pid,
        "slot": wrapper.get("slot"),
        "side": wrapper.get("side"),
        "base_conf_id": wrapper.get("base_conf_id"),
        "battle_uid": wrapper.get("battle_uid"),
    }
    if same_battle_pet(pet, w_pet):
        return True
    if p_pid is not None and w_pid is not None and p_pid == w_pid:
        if is_hidden_pet_id(p_pid):
            return pet.get("name") == (wrapper.get("name") or wrapper.get("pet_name"))
        return True
    return False


def is_mine(tracker: Any, side_value: Any) -> bool:
    """True if *side_value* represents the player side."""
    return side_is_player(
        side_value,
        battle_side_pets=tracker._battle_side_pets,
        player_slots=tracker._player_slots,
        opponent_slots=tracker._opponent_slots,
        my_pets=tracker.state["my_pets"],
    )


def bind_battle_side(
    tracker: Any,
    side_value: Any,
    pet: Optional[Dict[str, Any]],
    *,
    is_mine: Optional[bool] = None,
) -> None:
    side_num = tracker._side_int(side_value)
    if side_num is None or pet is None:
        return
    if is_mine is None:
        is_mine = pet in tracker.state["my_pets"]
    bind_side_slot(
        side_num,
        pet,
        battle_side_pets=tracker._battle_side_pets,
        player_slots=tracker._player_slots,
        opponent_slots=tracker._opponent_slots,
        is_mine=is_mine,
    )


def set_active_pet(tracker: Any, pet: Dict[str, Any]) -> None:
    if pet in tracker.state["my_pets"]:
        tracker.state["my_active"] = pet
    elif pet in tracker.state["opp_pets"]:
        tracker.state["opp_active"] = pet


def resolve_pet_for_side(
    tracker: Any,
    side_value: Any,
    *,
    bind_fallback: bool = False,
) -> Optional[Dict[str, Any]]:
    side_num = tracker._side_int(side_value)
    if side_num is not None:
        pet = tracker._battle_side_pets.get(side_num)
        if pet is not None:
            active_key = "my_active" if tracker._is_mine(side_value) else "opp_active"
            active = tracker.state.get(active_key)
            if (
                bind_fallback
                and pet.get("current_hp", 0) <= 0
                and active is not None
                and active.get("current_hp", 0) > 0
            ):
                tracker._bind_battle_side(side_num, active, is_mine=(active_key == "my_active"))
                return active
            return pet
        for candidate in tracker.state["my_pets"] + tracker.state["opp_pets"]:
            if candidate.get("slot") == side_num:
                tracker._bind_battle_side(side_num, candidate)
                return candidate

    active_key = "my_active" if tracker._is_mine(side_value) else "opp_active"
    active = tracker.state[active_key]
    if bind_fallback and side_num is not None and active is not None and active.get("current_hp", 0) <= 0:
        return None
    if bind_fallback and side_num is not None and active is not None:
        tracker._bind_battle_side(side_num, active, is_mine=(active_key == "my_active"))
    return active


def get_active_for_side(tracker: Any, side_value: Any) -> Optional[Dict[str, Any]]:
    return tracker._resolve_pet_for_side(side_value, bind_fallback=True)
