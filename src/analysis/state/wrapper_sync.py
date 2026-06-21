"""Round/action wrapper synchronization for BattleStateTracker."""
from __future__ import annotations

from typing import Any, Dict, List

from src.analysis.constants import OPCODE_ACTION_ACK
from src.analysis.pet_info import PetInfo, canonical_pet_name
from src.analysis.pet_identity import refresh_battle_uid


def pet_matches(pet: Dict[str, Any], wrapper: Dict[str, Any]) -> bool:
    """Legacy wrapper match helper kept for BattleStateTracker compatibility."""
    wrapper_pet_id = wrapper.get("pet_id") or wrapper.get("pet_gid")
    pet_id = pet.get("pet_id")
    if pet_id is not None and wrapper_pet_id is not None and pet_id == wrapper_pet_id:
        if pet_id == 20000000:
            wrapper_slot = wrapper.get("slot")
            pet_slot = pet.get("slot")
            if wrapper_slot is not None and pet_slot is not None and wrapper_slot == pet_slot:
                return True
            return pet.get("name") == wrapper.get("name")
        return True
    return False


def update_pets_from_wrappers(tracker: Any, wrappers: List[Dict[str, Any]]) -> None:
    """Refresh roster and active-pet state from round/action wrapper payloads."""
    replacement_candidates: Dict[str, Dict[str, Any]] = {}
    replacement_sides: Dict[str, Any] = {}
    replacement_ownership: Dict[str, bool] = {}
    side_counts = _wrapper_side_counts(wrappers)
    for wrapper in wrappers:
        side = wrapper.get("side")
        is_mine = side == 1 or side == "我方"
        pet_list = tracker.state["my_pets"] if is_mine else tracker.state["opp_pets"]
        active_key = "my_active" if is_mine else "opp_active"
        current_active = tracker.state.get(active_key)
        if side is None:
            matched_side = None
            matched_is_mine = False
            for candidate_is_mine, candidates in (
                (True, tracker.state["my_pets"]),
                (False, tracker.state["opp_pets"]),
            ):
                if any(tracker._stable_pet_matches(pet, wrapper) for pet in candidates):
                    matched_side = candidates
                    matched_is_mine = candidate_is_mine
                    break
            if matched_side is not None:
                pet_list = matched_side
                is_mine = matched_is_mine

        matched = None
        for pet in pet_list:
            if not tracker._stable_pet_matches(pet, wrapper):
                continue
            matched = pet
            _merge_wrapper_into_pet(tracker, pet, wrapper, is_mine=is_mine, side=side)
            break

        hydrated_placeholder = False
        if matched is None and _can_hydrate_supply_placeholder(current_active, pet_list):
            matched = current_active
            hydrated_placeholder = True
            _merge_wrapper_into_pet(tracker, matched, wrapper, is_mine=is_mine, side=side)

        if matched is None:
            pet_info = PetInfo.from_wrapper(wrapper).to_dict()
            if tracker._current_opcode == OPCODE_ACTION_ACK and wrapper.get("skills"):
                tracker._apply_battle_skill_pool(
                    pet_info,
                    wrapper.get("skills") or [],
                    source="action_ack.state_wrapper.skill_round_data",
                )
            refresh_battle_uid(pet_info)
            pet_list.append(pet_info)
            matched = pet_list[-1]
        elif hydrated_placeholder:
            matched.pop("supply_placeholder", None)
            pending_side = matched.pop("pending_supply_side", None)
            if pending_side is not None:
                tracker._bind_battle_side(pending_side, matched, is_mine=is_mine)

        if matched is not None and side is not None:
            tracker._bind_battle_side(side, matched, is_mine=is_mine)
        side_count = side_counts.get("my" if is_mine else "opp", 0)
        if matched is not None and side_count == 1:
            tracker.state[active_key] = matched
            tracker._bind_battle_side(side, matched, is_mine=is_mine)
            continue
        if (
            matched is not None
            and matched.get("current_hp", 0) > 0
            and (current_active is None or current_active.get("current_hp", 0) <= 0)
            and active_key not in replacement_candidates
        ):
            replacement_candidates[active_key] = matched
            replacement_sides[active_key] = side
            replacement_ownership[active_key] = is_mine

    for active_key, pet in replacement_candidates.items():
        current_active = tracker.state.get(active_key)
        if current_active is not None and current_active.get("current_hp", 0) > 0:
            continue
        tracker.state[active_key] = pet
        tracker._bind_battle_side(
            replacement_sides.get(active_key),
            pet,
            is_mine=replacement_ownership.get(active_key),
        )


def _wrapper_side_counts(wrappers: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"my": 0, "opp": 0}
    for wrapper in wrappers:
        side = wrapper.get("side")
        if side == 1 or side == "我方":
            counts["my"] += 1
        elif side is not None:
            counts["opp"] += 1
    return counts


def _can_hydrate_supply_placeholder(
    current_active: Dict[str, Any] | None,
    pet_list: List[Dict[str, Any]],
) -> bool:
    return (
        current_active is not None
        and current_active.get("supply_placeholder") is True
        and current_active in pet_list
    )


def _merge_wrapper_into_pet(
    tracker: Any,
    pet: Dict[str, Any],
    wrapper: Dict[str, Any],
    *,
    is_mine: bool,
    side: Any,
) -> None:
    """Apply a matched wrapper to an existing pet dict."""
    if "max_hp" in wrapper:
        pet["max_hp"] = wrapper["max_hp"]
    if "hp" in wrapper:
        new_hp = wrapper["hp"]
        if new_hp is not None and (
            is_mine
            or pet.get("supply_placeholder") is True
            or new_hp <= pet.get("current_hp", float("inf"))
        ):
            tracker._apply_hp_update(
                pet,
                event_kind="round_start",
                entry=wrapper,
                side=side,
                target_pet_id=pet.get("pet_id"),
                hp_result=new_hp,
                source_hint="round_start_wrapper",
            )
    protocol_name = wrapper.get("pet_name") or wrapper.get("name")
    if protocol_name and protocol_name != "?":
        pet["protocol_name"] = protocol_name
    if wrapper.get("pet_id") and wrapper["pet_id"] != 20000000:
        pet["pet_id"] = wrapper["pet_id"]
    if wrapper.get("level") is not None:
        pet["level"] = wrapper["level"]
    new_stats = wrapper.get("stats")
    if new_stats and len(new_stats) >= len(pet.get("stats", [])):
        pet["stats"] = new_stats
    if wrapper.get("base_id") is not None:
        pet["base_id"] = wrapper["base_id"]
    if wrapper.get("base_conf_id") is not None:
        pet["base_conf_id"] = wrapper["base_conf_id"]
        pet["base_id"] = wrapper["base_conf_id"]
    if protocol_name and protocol_name != "?" or wrapper.get("base_conf_id") is not None or wrapper.get("pet_id") is not None:
        pet["name"] = canonical_pet_name(
            base_conf_id=pet.get("base_conf_id"),
            pet_id=pet.get("pet_id"),
            protocol_name=pet.get("protocol_name") or protocol_name,
        )
    if wrapper.get("slot") is not None:
        pet["slot"] = wrapper["slot"]
    if wrapper.get("side") is not None:
        pet["side"] = wrapper["side"]
    if wrapper.get("base_skill_pool") is not None:
        pet["base_skill_pool"] = wrapper["base_skill_pool"]
    tracker._apply_wrapper_runtime_fields(pet, wrapper)
    if wrapper.get("passive_skill_id") is not None:
        pet["innate_skill_id"] = wrapper["passive_skill_id"]
    _merge_initial_buffs(tracker, pet, wrapper, is_mine=is_mine)
    _merge_wrapper_skills(tracker, pet, wrapper)
    if pet.get("base_speed") is None:
        battle_stats = wrapper.get("battle_stats") or []
        if len(battle_stats) >= 6 and battle_stats[5]:
            pet["base_speed"] = battle_stats[5]
    wrapper_energy = wrapper.get("energy")
    if wrapper_energy is not None and wrapper_energy > 0:
        pet["energy"] = min(10, wrapper_energy)
    if not pet.get("types") and wrapper.get("types"):
        pet["types"] = wrapper["types"]
    if pet["max_hp"] > 0:
        pet["hp_pct"] = pet["current_hp"] / pet["max_hp"]
    refresh_battle_uid(pet)


def _merge_initial_buffs(tracker: Any, pet: Dict[str, Any], wrapper: Dict[str, Any], *, is_mine: bool) -> None:
    wrapper_buffs = wrapper.get("initial_buffs", [])
    if not wrapper_buffs:
        return
    existing_ids = {buff["id"] for buff in pet.get("buffs", []) if "id" in buff}
    for buff in wrapper_buffs:
        if buff.get("id") not in existing_ids:
            pet.setdefault("buffs", []).append(
                tracker._enrich_wrapper_buff_for_pet(pet, buff, is_mine=is_mine)
            )


def _merge_wrapper_skills(tracker: Any, pet: Dict[str, Any], wrapper: Dict[str, Any]) -> None:
    equipped = wrapper.get("equipped_skills") or []
    if equipped and not pet.get("equipped_skills"):
        pet["skills"] = wrapper.get("skills", [])
        pet["equipped_skills"] = equipped
    if tracker._current_opcode == OPCODE_ACTION_ACK and wrapper.get("skills"):
        tracker._apply_battle_skill_pool(
            pet,
            wrapper.get("skills") or [],
            source="action_ack.state_wrapper.skill_round_data",
        )
