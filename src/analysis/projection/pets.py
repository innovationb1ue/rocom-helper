"""换宠 entry 状态投影。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.analysis.pet_identity import refresh_battle_uid


def project_change_pet(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    """简化版换宠投影：仅更新 active 指针，不修改宠物列表 HP。"""
    battle_pet_id = entry.get("battle_pet_id")
    new_pet_name = entry.get("new_pet_name")
    new_pet_id = entry.get("new_pet_id")
    new_base_conf_id = entry.get("new_pet_base_conf_id")
    if battle_pet_id is None:
        return

    is_opp = _is_opp_switch(entry, battle_pet_id)
    pet_list = state.get("opp_pets" if is_opp else "my_pets", [])
    active_key = "opp_active" if is_opp else "my_active"

    matched = _match_pet(
        pet_list,
        battle_pet_id=battle_pet_id,
        new_pet_id=new_pet_id,
        new_pet_name=new_pet_name,
        new_base_conf_id=new_base_conf_id,
        is_opp=is_opp,
    )
    if matched is not None:
        if matched.get("side") is None:
            matched["side"] = 401 if is_opp else 1
        if matched.get("slot") is None:
            matched["slot"] = battle_pet_id
        refresh_battle_uid(matched, side=401 if is_opp else 1)
        state[active_key] = matched


def _is_opp_switch(entry: Dict[str, Any], battle_pet_id: Any) -> bool:
    target_side = entry.get("target_side")
    if target_side is not None:
        return int(target_side) >= 401
    return int(battle_pet_id) >= 401


def _match_pet(
    pet_list: list[Dict[str, Any]],
    *,
    battle_pet_id: Any,
    new_pet_id: Any,
    new_pet_name: Any,
    new_base_conf_id: Any,
    is_opp: bool,
) -> Optional[Dict[str, Any]]:
    matched = _match_by_pet_id(pet_list, new_pet_id)
    if matched is None:
        matched = _match_by_name(pet_list, new_pet_name)
    if matched is None:
        matched = _match_by_base_conf_id(pet_list, new_base_conf_id)
    if matched is None and not is_opp:
        idx = int(battle_pet_id) - 1
        if 0 <= idx < len(pet_list):
            matched = pet_list[idx]
    return matched


def _match_by_pet_id(pet_list: list[Dict[str, Any]], new_pet_id: Any) -> Optional[Dict[str, Any]]:
    if new_pet_id is None or new_pet_id == 20000000:
        return None
    return next((pet for pet in pet_list if pet.get("pet_id") == new_pet_id), None)


def _match_by_name(pet_list: list[Dict[str, Any]], new_pet_name: Any) -> Optional[Dict[str, Any]]:
    if not new_pet_name:
        return None
    return next((pet for pet in pet_list if pet.get("name") == new_pet_name), None)


def _match_by_base_conf_id(pet_list: list[Dict[str, Any]], new_base_conf_id: Any) -> Optional[Dict[str, Any]]:
    if new_base_conf_id is None:
        return None
    fallback = None
    for pet in pet_list:
        if pet.get("base_conf_id") != new_base_conf_id:
            continue
        if pet.get("pet_id") != 20000000 or pet.get("stats") or pet.get("equipped_skills"):
            return pet
        if fallback is None:
            fallback = pet
    return fallback

