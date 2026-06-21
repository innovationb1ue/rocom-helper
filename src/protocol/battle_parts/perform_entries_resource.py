"""Resource-like perform entry handlers for action resolve."""
from __future__ import annotations

from typing import Any, Dict

from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    first_sub,
    maybe_signed64,
    normalize_skill_id,
    pick_first,
    skill_name,
)


def apply_sp_energy_change_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_SP_ENERGY_CHANGE from field 17."""
    out["kind"] = "sp_energy_change"
    em = first_sub(sg.get(17, []))
    if not em:
        return

    out["sp_change_type"] = pick_first(collect_varints(em, 1))
    ele_sub = first_sub(field_groups(em).get(2, []))
    if ele_sub:
        out["sp_element"] = {
            "dam_type": pick_first(collect_varints(ele_sub, 1)),
            "stack": pick_first(collect_varints(ele_sub, 2)),
        }
    out["sp_change_src"] = pick_first(collect_varints(em, 3))
    out["caster_id"] = pick_first(collect_varints(em, 4))
    out["target_id"] = pick_first(collect_varints(em, 5))
    cv = pick_first(collect_varints(em, 6))
    rv = pick_first(collect_varints(em, 7))
    out["change_value"] = maybe_signed64(cv) if cv is not None else None
    out["real_change_value"] = maybe_signed64(rv) if rv is not None else None


def apply_sp_energy_trigger_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_SP_ENERGY_TRIGGER from field 16."""
    out["kind"] = "sp_energy_trigger"
    em = first_sub(sg.get(16, []))
    if not em:
        return

    out["dam_type"] = pick_first(collect_varints(em, 1))
    out["trigger_type"] = pick_first(collect_varints(em, 2))
    out["caster_id"] = pick_first(collect_varints(em, 3))
    old_raw = pick_first(collect_varints(em, 4))
    new_raw = pick_first(collect_varints(em, 5))
    out["old_skill_id"] = normalize_skill_id(old_raw) if old_raw else None
    out["old_skill_name"] = skill_name(out["old_skill_id"]) if out["old_skill_id"] else None
    out["new_skill_id"] = normalize_skill_id(new_raw) if new_raw else None
    out["new_skill_name"] = skill_name(out["new_skill_id"]) if out["new_skill_id"] else None
