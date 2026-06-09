"""Effect-related perform entry extractors for battle action resolve."""
from __future__ import annotations

from typing import Any, Dict, List

from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    first_sub,
    normalize_skill_id,
    pick_first,
    side_name,
    skill_name,
    _attach_buff_meta,
    _attach_buffbase_meta,
    _attach_skill_meta,
    _extract_actor_target,
)


def apply_effect_apply_entry(out: Dict[str, Any], groups: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_EFFECT_APPLY fields and related skill refs."""
    out["kind"] = "effect_apply"
    em = first_sub(groups.get(4, []))
    if em:
        _extract_actor_target(em, out)
        out["effect_id"] = pick_first(collect_varints(em, 3))
        out["effect_stage"] = pick_first(collect_varints(em, 4))
        _attach_buff_meta(out, out.get("effect_id"))

    ir = first_sub(groups.get(12, []))
    related: List[Dict[str, Any]] = []
    if ir:
        for child in field_groups(ir).get(3, []):
            cs = child.get("sub")
            if not cs:
                continue
            sx = pick_first(collect_varints(cs, 2), low=100_000)
            rsid = normalize_skill_id(sx)
            owner = pick_first(collect_varints(cs, 1))
            item: Dict[str, Any] = {
                "owner_side": owner,
                "owner_side_name": side_name(owner),
                "skill_id_x100": sx,
                "skill_id": rsid,
                "skill_name": skill_name(rsid),
                "arg3": pick_first(collect_varints(cs, 3)),
                "arg4": pick_first(collect_varints(cs, 4)),
            }
            _attach_skill_meta(item, rsid)
            related.append(item)
    if related:
        out["related_skills"] = related


def apply_buff_trigger_entry(out: Dict[str, Any], groups: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_BUFF_TRIGGER fields."""
    out["kind"] = "buff_trigger"
    out["legacy_kind"] = "effect_stage"
    out["aliases"] = ["effect_stage"]
    em = first_sub(groups.get(5, []))
    if em:
        _extract_actor_target(em, out)
        out["effect_id"] = pick_first(collect_varints(em, 3))
        out["buff_id"] = out["effect_id"]
        out["buffbase_ids"] = collect_varints(em, 6)
        out["perform_type"] = pick_first(collect_varints(em, 7))
        out["need_select_pet"] = bool(pick_first(collect_varints(em, 8)) or 0)
        out["frozen_death"] = bool(pick_first(collect_varints(em, 9)) or 0)
        out["effect_base"] = out["buffbase_ids"][0] if out.get("buffbase_ids") else None
        _attach_buff_meta(out, out.get("effect_id"))
        _attach_buffbase_meta(out, out.get("effect_base"))


def apply_effect_link_entry(out: Dict[str, Any], groups: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_EFFECT_LINK fields."""
    out["kind"] = "effect_link"
    lm = first_sub(groups.get(15, []))
    if lm:
        _extract_actor_target(lm, out)
        out["effect_id"] = pick_first(collect_varints(lm, 3))
        _attach_buff_meta(out, out.get("effect_id"))


def apply_effect_trigger_entry(out: Dict[str, Any], groups: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_EFFECT_TRIGGER fields."""
    out["kind"] = "effect_trigger"
    em = first_sub(groups.get(13, []))
    if em:
        _extract_actor_target(em, out)
        out["effect_id"] = pick_first(collect_varints(em, 3))
        out["trigger_result"] = pick_first(collect_varints(em, 5))
        out["trigger_params"] = collect_varints(em, 6)
        _attach_buff_meta(out, out.get("effect_id"))
