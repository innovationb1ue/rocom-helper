"""Pet runtime synchronization helpers for BattleStateTracker."""
from __future__ import annotations

import copy
from typing import Any, Dict

from src.analysis.reflect_effects import REFLECT_BUFF_ID
from src.data.loader import enrich_buff_modifiers


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
        return
    for key in ("name", "level", "base_conf_id", "types", "max_hp"):
        if sync.get(key) is not None:
            pet[key] = sync[key]
    if sync.get("equipped_skills"):
        pet["runtime_equipped_skills"] = sync["equipped_skills"]
    if sync.get("skill_round_data"):
        tracker._apply_battle_skill_pool(
            pet,
            sync["skill_round_data"],
            source="sync_data.pet_info.skill_round_data",
        )


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
    for sync in sync_data.get("pet_sync", []):
        tracker._apply_pet_sync(sync)
    for sync in sync_data.get("skill_sync", []):
        sync.setdefault("source", "skill_sync")
        tracker._update_skill_runtime(tracker._pet_for_sync_id(sync.get("pet_id")), sync)
    for sync in sync_data.get("skill_change_sync", []):
        sync.setdefault("source", "skill_change_sync")
        tracker._update_skill_runtime(tracker._pet_for_sync_id(sync.get("pet_id")), sync)
    for sync in sync_data.get("pet_info", []):
        tracker._apply_pet_info_sync(sync)
    # role_sync/comm_sync/task_infos are retained in compact history only.


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
