"""Lifecycle opcode handlers for BattleStateTracker."""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict

from src.analysis.pet_info import PetInfo
from src.analysis.pet_identity import refresh_battle_uid

logger = logging.getLogger(__name__)


def handle_battle_enter(tracker: Any, detail: Dict[str, Any]) -> None:
    """Initialize battle metadata, field context, rosters, and active pets."""
    tracker._opponent_slots.clear()
    tracker._player_slots.clear()
    tracker._battle_side_pets.clear()

    tracker.state["battle_id"] = detail.get("battle_id")
    tracker.state["battle_mode"] = detail.get("battle_mode")
    tracker.state["round"] = detail.get("round", 0)
    tracker.state["max_round"] = detail.get("max_round", 0)
    tracker.state["result"] = None
    tracker.state["events"] = []
    tracker.state["phase"] = "selecting"

    weather_id = detail.get("weather_id")
    weather = {
        "id": weather_id,
        "name": tracker._weather_name(weather_id),
        "expire_round": detail.get("weather_expire_round"),
        "changed_at_round": tracker.state["round"],
        "source": "battle_enter",
    }
    tracker.state["field_context"] = {
        "weather_current": weather,
        "weather_history": [copy.deepcopy(weather)] if weather_id is not None else [],
        "global_events": [],
        "perform_groups": [],
        "sync_events": [],
        "item_sync_events": [],
        "damage_ledger": [],
    }
    tracker._set_weather_current(weather)

    my_pets = []
    opp_pets = []
    for wrapper in detail.get("wrappers", []):
        pet_info = PetInfo.from_wrapper(wrapper, default_energy=10).to_dict()
        tracker._apply_wrapper_runtime_fields(pet_info, wrapper)
        equipped = wrapper.get("equipped_skills") or []
        side = wrapper.get("side")
        side_label = "MY" if (side == 1 or side == "我方") else "OPP"
        logger.info(
            "[%s] %s: %d equipped skills (source=%s) %s",
            side_label,
            pet_info["name"],
            len(equipped),
            wrapper.get("skill_source", "?"),
            [skill.get("skill_name", "?") for skill in equipped],
        )
        if side == 1 or side == "我方":
            my_pets.append(pet_info)
            if pet_info.get("slot") is not None:
                tracker._bind_battle_side(pet_info["slot"], pet_info, is_mine=True)
        else:
            opp_pets.append(pet_info)
            if pet_info.get("slot") is not None:
                tracker._bind_battle_side(pet_info["slot"], pet_info, is_mine=False)

    tracker.state["my_pets"] = my_pets
    tracker.state["opp_pets"] = opp_pets
    for pet in my_pets:
        refresh_battle_uid(pet, side=1)
    for pet in opp_pets:
        refresh_battle_uid(pet, side=401)
    if my_pets:
        tracker.state["my_active"] = my_pets[0]
        tracker._bind_battle_side(1, my_pets[0], is_mine=True)
    if opp_pets:
        tracker.state["opp_active"] = opp_pets[0]
        tracker._bind_battle_side(401, opp_pets[0], is_mine=False)


def handle_round_start(tracker: Any, detail: Dict[str, Any]) -> None:
    tracker.state["round"] = detail.get("round", tracker.state["round"] + 1)
    tracker.state["phase"] = "resolving"
    tracker._update_pets_from_wrappers(detail.get("wrappers", []))


def handle_action_ack(tracker: Any, detail: Dict[str, Any]) -> None:
    wrappers = detail.get("state_wrappers") or detail.get("wrappers") or []
    if wrappers:
        tracker._update_pets_from_wrappers(wrappers)


def handle_battle_finish(tracker: Any, detail: Dict[str, Any]) -> None:
    tracker.state["result"] = detail.get("result_name", "UNKNOWN")
    tracker.state["phase"] = "finished"
    for finish_pet in detail.get("finish_pet_infos", []):
        pet_id = finish_pet.get("pet_gid")
        remain = finish_pet.get("remain_hp", 0)
        for pet in tracker.state["my_pets"] + tracker.state["opp_pets"]:
            if pet.get("pet_id") == pet_id:
                tracker._apply_hp_update(
                    pet,
                    event_kind="battle_finish",
                    entry=finish_pet,
                    side=pet.get("side"),
                    target_pet_id=pet_id,
                    hp_result=remain,
                    source_hint="battle_finish",
                )


def handle_skill_select(_tracker: Any, _detail: Dict[str, Any]) -> None:
    """Client intent is recorded in the raw event log only."""


def handle_special_refresh(tracker: Any, detail: Dict[str, Any]) -> None:
    refresh_kind = detail.get("kind") or detail.get("action_name")
    if refresh_kind not in ("energy_bottle", "能量瓶"):
        return
    target_side = detail.get("side")
    active_key = "my_active" if tracker._is_mine(target_side) else "opp_active"
    active = tracker.state[active_key]
    if active is not None:
        active["energy"] = min(10, active.get("energy", 5) + detail.get("energy_delta", 3))


def handle_skill_declare(tracker: Any, detail: Dict[str, Any]) -> None:
    skill_id = detail.get("skill_id")
    actor_side = detail.get("actor_side")
    if skill_id is None or actor_side is None:
        return
    active = tracker._get_active_for_side(actor_side)
    if active is None:
        return
    used = active.setdefault("used_skills", [])
    if not any(skill.get("skill_id") == skill_id for skill in used):
        item = {"skill_id": skill_id}
        if detail.get("skill_name"):
            item["skill_name"] = detail["skill_name"]
        used.append(item)


def handle_round_flow(tracker: Any, detail: Dict[str, Any]) -> None:
    tracker.state["round"] = detail.get("round", tracker.state["round"])
