"""Skill-related perform entry handlers for action resolve."""
from __future__ import annotations

from typing import Any, Dict

from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    first_sub,
    normalize_skill_id,
    pick_first,
    skill_name,
    _attach_skill_meta,
    _extract_actor_target,
)


def apply_role_skill_cast_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_ROLE_SKILL_CAST from field 37."""
    out["kind"] = "role_skill_cast"
    rm = first_sub(sg.get(37, []))
    if not rm:
        return

    out["caster_uin"] = pick_first(collect_varints(rm, 1))
    skill_raw = pick_first(collect_varints(rm, 2))
    sid = normalize_skill_id(skill_raw) if skill_raw else None
    out["skill_id"] = sid
    out["skill_name"] = skill_name(sid) if sid else None
    if sid:
        _attach_skill_meta(out, sid)
    out["pet_id"] = pick_first(collect_varints(rm, 3))
    out["is_call_success"] = bool(pick_first(collect_varints(rm, 4)) or 0)


def apply_combo_skill_cast_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_COMBO_SKILL from field 38."""
    out["kind"] = "combo_skill_cast"
    cm = first_sub(sg.get(38, []))
    if not cm:
        return

    _extract_actor_target(cm, out)
    out["caster_id"] = pick_first(collect_varints(cm, 1))
    out["target_id"] = collect_varints(cm, 2)
    skill_id_x100 = pick_first(collect_varints(cm, 3), low=100_000)
    sid = normalize_skill_id(skill_id_x100)
    out["skill_id_x100"] = skill_id_x100
    out["skill_id"] = sid
    out["skill_name"] = skill_name(sid)
    _attach_skill_meta(out, sid)
    out["combo_index"] = pick_first(collect_varints(cm, 8))
    out["combo_count"] = pick_first(collect_varints(cm, 9))


def apply_skill_pos_change_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_SKILL_POS_CHANGE from field 46."""
    out["kind"] = "skill_pos_change"
    cm = first_sub(sg.get(46, []))
    if not cm:
        return

    out["pet_id"] = pick_first(collect_varints(cm, 1))
    pos_infos = []
    for child in field_groups(cm).get(2, []):
        cs = child.get("sub")
        if cs is None:
            continue
        info = {
            "skill_id": pick_first(collect_varints(cs, 1)),
            "old_pos": pick_first(collect_varints(cs, 2)),
            "new_pos": pick_first(collect_varints(cs, 3)),
            "change_type": pick_first(collect_varints(cs, 4)),
        }
        if info["skill_id"]:
            info["skill_name"] = skill_name(info["skill_id"])
        pos_infos.append(info)
    if pos_infos:
        out["skill_pos_infos"] = pos_infos


def apply_special_move_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_SPECIAL_MOVE from field 47."""
    out["kind"] = "special_move"
    sm = first_sub(sg.get(47, []))
    if not sm:
        return

    out["pet_id"] = pick_first(collect_varints(sm, 1))
    out["special_move_id"] = pick_first(collect_varints(sm, 2))
    out["special_move_type"] = pick_first(collect_varints(sm, 3))
    out["round"] = pick_first(collect_varints(sm, 4))
    skill_raw = pick_first(collect_varints(sm, 5))
    sid = normalize_skill_id(skill_raw) if skill_raw else None
    out["skill_id"] = sid
    out["skill_name"] = skill_name(sid) if sid else None
