"""Pet lifecycle perform entry handlers for action resolve."""
from __future__ import annotations

from typing import Any, Dict

from src.protocol.proto_core import (
    SDT_TO_TYPE,
    collect_varints,
    field_groups,
    first_sub,
    first_text,
    pick_first,
    side_name,
    _extract_actor_target,
)


def apply_defeat_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_DEFEAT from field 9."""
    out["kind"] = "defeat"
    dm = first_sub(sg.get(9, []))
    if dm:
        _extract_actor_target(dm, out)
        out["defeat_arg"] = pick_first(collect_varints(dm, 3))


def apply_revive_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_REVIVE from field 10."""
    out["kind"] = "revive"
    rm = first_sub(sg.get(10, []))
    if rm:
        _extract_actor_target(rm, out)


def apply_change_pet_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_CHANGE_PET from field 18."""
    out["kind"] = "change_pet"
    cm = first_sub(sg.get(18, []))
    if not cm:
        return

    _extract_actor_target(cm, out)
    out["rest_pet_id"] = pick_first(collect_varints(cm, 2))
    out["battle_pet_id"] = pick_first(collect_varints(cm, 3))
    out["is_cmd"] = pick_first(collect_varints(cm, 5))

    pet_wrapper = first_sub(field_groups(cm).get(4, []))
    if not pet_wrapper:
        return

    pwg = field_groups(pet_wrapper)
    info_sub = first_sub(pwg.get(2, []))
    if info_sub:
        out["new_pet_id"] = pick_first(collect_varints(info_sub, 2), low=1)
        out["new_pet_name"] = first_text(info_sub, 3)
        out["new_pet_types"] = [SDT_TO_TYPE.get(v, v) for v in collect_varints(info_sub, 6)]
        out["new_pet_level"] = pick_first(collect_varints(info_sub, 10), low=1, high=100)
        out["new_pet_base_conf_id"] = pick_first(collect_varints(info_sub, 15))

    state_sub = first_sub(pwg.get(1, []))
    if not state_sub:
        return

    if not out.get("new_pet_name"):
        out["new_pet_id"] = pick_first(collect_varints(state_sub, 21), low=1)
        out["new_pet_name"] = first_text(state_sub, 23)

    ds = collect_varints(state_sub, 6)
    if len(ds) >= 7:
        out["new_pet_battle_stats"] = ds[1:7]
    if len(ds) >= 26:
        out["new_pet_current_hp"] = ds[25]
        out["new_pet_max_hp"] = ds[1]

    raw_pet_energy = pick_first(collect_varints(info_sub, 33)) if info_sub else None
    if raw_pet_energy is not None and raw_pet_energy > 0:
        out["new_pet_energy"] = raw_pet_energy

    out["new_pet_passive_skill_id"] = pick_first(collect_varints(state_sub, 64))


def apply_change_model_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_CHANGE_MODEL from field 32."""
    out["kind"] = "change_model"
    cm = first_sub(sg.get(32, []))
    if not cm:
        return

    pet_id = pick_first(collect_varints(cm, 1))
    out["pet_id"] = pet_id
    out["actor_side"] = pet_id
    out["actor_side_name"] = side_name(pet_id)
    out["target_side"] = pet_id
    out["target_side_name"] = side_name(pet_id)
    out["old_base_id"] = pick_first(collect_varints(cm, 2))
    out["role_magic_flag"] = pick_first(collect_varints(cm, 4))

    pet_wrapper = first_sub(field_groups(cm).get(3, []))
    if not pet_wrapper:
        return

    pwg = field_groups(pet_wrapper)
    state_sub = first_sub(pwg.get(1, []))
    if state_sub:
        out["model_pet_id"] = pick_first(collect_varints(state_sub, 21), low=1)
        out["model_base_id"] = pick_first(collect_varints(state_sub, 22), low=1)
        out["model_pet_name"] = first_text(state_sub, 23)
        ds = collect_varints(state_sub, 6)
        if len(ds) >= 7:
            out["model_battle_stats"] = ds[1:7]
        if len(ds) >= 26:
            out["model_current_hp"] = ds[25]
            out["model_max_hp"] = ds[1]

    info_sub = first_sub(pwg.get(2, []))
    if info_sub:
        out["original_pet_id"] = pick_first(collect_varints(info_sub, 2), low=1)
        out["original_pet_name"] = first_text(info_sub, 3)
        out["original_pet_types"] = [SDT_TO_TYPE.get(v, v) for v in collect_varints(info_sub, 6)]
        out["original_pet_level"] = pick_first(collect_varints(info_sub, 10), low=1, high=100)
        out["original_base_conf_id"] = pick_first(collect_varints(info_sub, 15))


def apply_supply_pet_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_SUPPLY_PET from field 45."""
    out["kind"] = "supply_pet"
    sm = first_sub(sg.get(45, []))
    if not sm:
        return

    out["player_id"] = pick_first(collect_varints(sm, 1))
    pet_infos = []
    for child in field_groups(sm).get(2, []):
        cs = child.get("sub")
        if cs is None:
            continue
        pet_infos.append({
            "pet_id": pick_first(collect_varints(cs, 1)),
            "pet_pos": pick_first(collect_varints(cs, 2)),
        })
    if pet_infos:
        out["supply_pets"] = pet_infos
