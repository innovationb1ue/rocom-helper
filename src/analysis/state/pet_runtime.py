"""Pet runtime synchronization helpers for BattleStateTracker."""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from src.analysis.pet_info import canonical_pet_name
from src.analysis.pet_identity import refresh_battle_uid
from src.analysis.reflect_effects import REFLECT_BUFF_ID
from src.analysis.state import side_resolver
from src.data.loader import enrich_buff_modifiers, get_pet_skill_meta


WRAPPER_RUNTIME_KEYS = (
    "state_bits", "sp_energy", "extra_resist_type", "in_battle_round",
    "counter_round", "revive_round", "revive_rounds", "charging_skill_id",
    "remain_buff_infos", "extra_sdt", "changed_attr", "dead_round",
    "dead_cnt", "using_buffs", "triggered_buffs", "max_energy",
    "speed_min", "speed_max", "owner_uin", "last_up_round",
    "last_down_round", "charging_skill_energy",
)


def apply_pet_sync(tracker: Any, sync: Dict[str, Any]) -> None:
    pet = tracker._pet_for_sync_id(sync.get("pet_id"))
    if pet is None:
        if sync.get("hp_result") is not None or sync.get("hp_change") is not None:
            tracker._apply_hp_update(
                None,
                event_kind="pet_sync",
                entry=sync,
                side=sync.get("pet_id"),
                target_pet_id=sync.get("pet_id"),
                hp_change=sync.get("hp_change"),
                hp_result=sync.get("hp_result"),
                actual_damage=sync.get("actual_damage") or sync.get("original_damage"),
                source_hint="pet_sync",
            )
        return
    if sync.get("hp_result") is not None or sync.get("hp_change") is not None:
        tracker._apply_hp_update(
            pet,
            event_kind="pet_sync",
            entry=sync,
            side=sync.get("pet_id"),
            target_pet_id=sync.get("pet_id"),
            hp_change=sync.get("hp_change"),
            hp_result=sync.get("hp_result"),
            actual_damage=sync.get("actual_damage") or sync.get("original_damage"),
            source_hint="pet_sync",
        )
    if sync.get("energy_result") is not None:
        max_energy = sync.get("max_energy") or pet.get("max_energy") or 10
        pet["energy"] = max(0, min(max_energy, sync["energy_result"]))
    if sync.get("max_energy") is not None:
        pet["max_energy"] = sync["max_energy"]
    if sync.get("state_bit_results") is not None:
        pet["state_bit_results"] = sync["state_bit_results"]
    if sync.get("state_bit_change_pos") is not None:
        pet["state_bit_change_pos"] = sync["state_bit_change_pos"]
    if sync.get("shield_result") is not None:
        pet["shield"] = sync["shield_result"]
    if sync.get("damage_result") is not None:
        pet["last_damage_result"] = sync["damage_result"]
    if sync.get("original_damage") is not None:
        pet["last_original_damage"] = sync["original_damage"]
    if sync.get("charging_skill_id") is not None:
        pet["charging_skill_id"] = sync["charging_skill_id"]
    if sync.get("attr_type") is not None:
        pet.setdefault("attr_changes", []).append({
            "attr_type": sync.get("attr_type"),
            "attr_change": sync.get("attr_change"),
            "attr_result": sync.get("attr_result"),
            "round": tracker.state.get("round", 0),
        })
    if sync.get("instant_kill_result") is not None:
        pet["instant_kill_result"] = sync["instant_kill_result"]
    if sync.get("revive_round") is not None:
        pet["revive_round"] = sync["revive_round"]
    if sync.get("revive_rounds") is not None:
        pet["revive_rounds"] = sync["revive_rounds"]
    if sync.get("triggered_buffs") is not None:
        pet["triggered_buffs"] = sync["triggered_buffs"]
    if sync.get("buff_id") is not None and sync.get("buff_stack_result") is not None:
        buffs = pet.setdefault("buffs", [])
        existing = next((b for b in buffs if b.get("id") == sync["buff_id"]), None)
        if sync["buff_stack_result"] <= 0:
            pet["buffs"] = [b for b in buffs if b.get("id") != sync["buff_id"]]
        elif existing:
            existing["stage"] = sync["buff_stack_result"]
            existing.update(enrich_buff_modifiers(existing))
        else:
            buffs.append(enrich_buff_modifiers({
                "id": sync["buff_id"],
                "name": str(sync["buff_id"]),
                "stage": sync["buff_stack_result"],
            }))
        if sync["buff_id"] != REFLECT_BUFF_ID and sync["buff_stack_result"] > 0:
            tracker._attach_reflect_confirmed_effect(
                pet,
                sync,
                source="pet_sync",
            )


def apply_pet_info_sync(tracker: Any, sync: Dict[str, Any]) -> None:
    pet = tracker._pet_for_sync_id(sync.get("pet_id"))
    if pet is None:
        pet = _find_or_create_pet_from_info_sync(tracker, sync)
    if pet is None:
        return
    for key in ("name", "level", "base_conf_id", "types", "max_hp"):
        if sync.get(key) is not None:
            pet[key] = sync[key]
    if sync.get("pet_id") is not None:
        pet["pet_id"] = sync["pet_id"]
    if sync.get("base_conf_id") is not None:
        pet["base_id"] = sync["base_conf_id"]
    protocol_name = sync.get("name")
    if protocol_name:
        pet["protocol_name"] = protocol_name
    if protocol_name or sync.get("base_conf_id") is not None or sync.get("pet_id") is not None:
        pet["name"] = canonical_pet_name(
            base_conf_id=pet.get("base_conf_id"),
            pet_id=pet.get("pet_id"),
            protocol_name=pet.get("protocol_name") or protocol_name,
        )
    if pet.get("max_hp", 0) > 0:
        if pet.get("current_hp", 0) <= 0 and not pet.get("hp_trace"):
            pet["current_hp"] = pet["max_hp"]
        pet["hp_pct"] = pet["current_hp"] / pet["max_hp"]
    if sync.get("equipped_skills"):
        pet["runtime_equipped_skills"] = sync["equipped_skills"]
    if sync.get("skill_round_data"):
        tracker._apply_battle_skill_pool(
            pet,
            sync["skill_round_data"],
            source="sync_data.pet_info.skill_round_data",
        )
    if pet.get("base_skill_pool") is None and pet.get("base_id") is not None:
        skill_pool = get_pet_skill_meta(pet["base_id"])
        if isinstance(skill_pool, dict):
            pet["base_skill_pool"] = skill_pool.get("level_skills") or []
    side_value = sync.get("source_side")
    if side_value is not None and side_resolver.is_battle_side_value(tracker, side_value):
        side_num = tracker._side_int(side_value)
        is_mine = tracker._is_mine(side_value)
        if pet.get("side") is None:
            pet["side"] = 1 if is_mine else 401
        if pet.get("slot") is None and side_num is not None:
            pet["slot"] = side_num
        refresh_battle_uid(pet, side=1 if is_mine else 401)
        tracker._bind_battle_side(side_value, pet, is_mine=is_mine)
        tracker._set_active_pet(pet)


def apply_wrapper_runtime_fields(pet: Dict[str, Any], wrapper: Dict[str, Any]) -> None:
    for key in WRAPPER_RUNTIME_KEYS:
        if wrapper.get(key) not in (None, [], {}):
            pet[key] = copy.deepcopy(wrapper[key])


def enrich_wrapper_buff_for_pet(
    pet: Dict[str, Any],
    buff: Dict[str, Any],
    *,
    is_mine: bool,
) -> Dict[str, Any]:
    return enrich_buff_modifiers(buff)


def apply_entry_sync_data(tracker: Any, entry: Dict[str, Any]) -> None:
    sync_data = entry.get("sync_data") or {}
    if not sync_data:
        return
    tracker._record_sync_event(entry)
    tracker._record_item_sync_events(entry)
    _apply_role_resource_sync(tracker, entry)
    for sync in sync_data.get("pet_sync", []):
        tracker._apply_pet_sync(sync)
    for sync in sync_data.get("skill_sync", []):
        sync.setdefault("source", "skill_sync")
        tracker._update_skill_runtime(tracker._pet_for_sync_id(sync.get("pet_id")), sync)
    for sync in sync_data.get("skill_change_sync", []):
        sync.setdefault("source", "skill_change_sync")
        tracker._update_skill_runtime(tracker._pet_for_sync_id(sync.get("pet_id")), sync)
    pet_info_side = _pet_info_source_side(tracker, entry)
    for sync in sync_data.get("pet_info", []):
        if pet_info_side is not None:
            sync.setdefault("source_side", pet_info_side)
        tracker._apply_pet_info_sync(sync)
    # role_sync/comm_sync/task_infos are retained in compact history only.


def _apply_role_resource_sync(tracker: Any, entry: Dict[str, Any]) -> None:
    """Project explicit role/battle resource syncs into state.

    These fields are protocol resources, not pet defeat counters.  They are
    projected for display/diagnostics only; battle_finish remains the only
    source that can finalize the battle.
    """
    sync_data = entry.get("sync_data") or {}
    resource_events = tracker.state.setdefault("role_resource_events", [])
    role_resources = tracker.state.setdefault("role_resources", {})
    battle_resource = tracker.state.setdefault("battle_resource", {})
    common = {
        "round": tracker.state.get("round", 0),
        "packet_index": (tracker._current_event_detail or {}).get("packet_index"),
        "group_id": entry.get("group_id"),
        "event_ordinal": entry.get("event_ordinal"),
    }

    for sync in sync_data.get("role_sync", []) or []:
        if not any(key in sync for key in ("role_energy_change", "role_energy_result", "remain_use_cnt", "allow_use_cnt")):
            continue
        role_key = str(sync.get("role_uin") if sync.get("role_uin") is not None else "unknown")
        current = role_resources.setdefault(role_key, {})
        if sync.get("role_uin") is not None:
            current["role_uin"] = sync["role_uin"]
        for key in ("role_energy_result", "remain_use_cnt", "allow_use_cnt", "allow_use_cnt_inbattle"):
            if sync.get(key) is not None:
                current[key] = sync[key]
        event = {
            **common,
            "source": "role_sync",
            "role_key": role_key,
            "role_uin": sync.get("role_uin"),
            "role_energy_change": sync.get("role_energy_change"),
            "role_energy_result": sync.get("role_energy_result"),
            "remain_use_cnt": sync.get("remain_use_cnt"),
            "allow_use_cnt": sync.get("allow_use_cnt"),
            "allow_use_cnt_inbattle": sync.get("allow_use_cnt_inbattle"),
        }
        resource_events.append({k: v for k, v in event.items() if v is not None})

    for sync in sync_data.get("comm_sync", []) or []:
        if not any(key in sync for key in ("sp_energy_result", "final_battle_energy_result")):
            continue
        for key in ("sp_energy_type", "sp_energy_result", "final_battle_energy_result"):
            if sync.get(key) is not None:
                battle_resource[key] = sync[key]
        event = {
            **common,
            "source": "comm_sync",
            "sp_energy_type": sync.get("sp_energy_type"),
            "sp_energy_change": sync.get("sp_energy_change"),
            "sp_energy_result": sync.get("sp_energy_result"),
            "final_battle_energy_change": sync.get("final_battle_energy_change"),
            "final_battle_energy_result": sync.get("final_battle_energy_result"),
        }
        resource_events.append({k: v for k, v in event.items() if v is not None})

    if len(resource_events) > 200:
        del resource_events[:len(resource_events) - 200]


def _pet_info_source_side(tracker: Any, entry: Dict[str, Any]) -> Optional[Any]:
    for key in ("target_side", "actor_side", "damage_target_side"):
        value = entry.get(key)
        if side_resolver.is_battle_side_value(tracker, value):
            return value
    return None


def _find_or_create_pet_from_info_sync(tracker: Any, sync: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    side_value = sync.get("source_side")
    is_mine = tracker._is_mine(side_value) if side_value is not None else False
    pet_list = tracker.state["my_pets"] if is_mine else tracker.state["opp_pets"]
    pet_id = sync.get("pet_id")
    base_conf_id = sync.get("base_conf_id")
    for pet in pet_list:
        if pet_id is not None and pet.get("pet_id") == pet_id:
            return pet
        if base_conf_id is not None and pet.get("base_conf_id") == base_conf_id:
            return pet
    side_num = tracker._side_int(side_value)
    if side_num is not None:
        for pet in pet_list:
            if pet.get("slot") == side_num:
                return pet
    if side_value is None or not side_resolver.is_battle_side_value(tracker, side_value):
        return None
    pet = _new_pet_from_info_sync(tracker, sync, side_value=side_value, is_mine=is_mine)
    pet_list.append(pet)
    return pet


def _new_pet_from_info_sync(
    tracker: Any,
    sync: Dict[str, Any],
    *,
    side_value: Any,
    is_mine: bool,
) -> Dict[str, Any]:
    side_num = tracker._side_int(side_value)
    max_hp = sync.get("max_hp") or 0
    base_conf_id = sync.get("base_conf_id")
    pet = {
        "pet_id": sync.get("pet_id"),
        "name": canonical_pet_name(
            base_conf_id=base_conf_id,
            pet_id=sync.get("pet_id"),
            protocol_name=sync.get("name"),
        ),
        "types": sync.get("types") or [],
        "current_hp": max_hp,
        "max_hp": max_hp,
        "hp_pct": 1.0 if max_hp else 0.0,
        "energy": 10,
        "buffs": [],
        "initial_buff_ids": [],
        "innate_skill_id": None,
        "level": sync.get("level"),
        "slot": side_num,
        "side": 1 if is_mine else 401,
        "stats": [{"name": "HP", "total": max_hp}] if max_hp else [],
        "skills": [],
        "equipped_skills": [],
        "base_id": base_conf_id,
        "base_conf_id": base_conf_id,
        "base_skill_pool": None,
        "combo_bonus": 0,
        "poison_stacks": 0,
        "used_skills": [],
        "base_speed": None,
        "protocol_name": sync.get("name"),
    }
    if pet["base_id"] is not None:
        skill_pool = get_pet_skill_meta(pet["base_id"])
        if isinstance(skill_pool, dict):
            pet["base_skill_pool"] = skill_pool.get("level_skills") or []
    refresh_battle_uid(pet, side=1 if is_mine else 401)
    return pet


def apply_pet_skill_updates(tracker: Any, entry: Dict[str, Any]) -> None:
    for update in entry.get("pet_skill_updates", []) or []:
        pet = tracker._pet_for_sync_id(update.get("pet_id"))
        for skill in update.get("skills", []) or []:
            skill.setdefault("source", "data_update.pet_skill")
            tracker._update_skill_runtime(pet, skill)
        tracker._apply_battle_skill_pool(
            pet,
            update.get("skills") or [],
            source="data_update.pet_skill.skills",
        )
