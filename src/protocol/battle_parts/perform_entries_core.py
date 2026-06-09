"""Core numeric perform entry extractors for battle action resolve."""
from __future__ import annotations

from typing import Any, Dict

from src.protocol.battle_actions import _extract_skill_ref
from src.protocol.battle_parts.sync_common import _pick_sync_value
from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    first_sub,
    maybe_signed64,
    pick_first,
    side_name,
    _extract_actor_target,
)


def apply_skill_cast_entry(out: Dict[str, Any], groups: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_SKILL_CAST fields."""
    out["kind"] = "skill_cast"
    out.update(_extract_skill_ref(first_sub(groups.get(3, [])), skill_field=3))
    ir_sub = first_sub(groups.get(12, []))
    detail = first_sub(field_groups(ir_sub).get(2, [])) if ir_sub else None
    if detail:
        rd = pick_first(collect_varints(detail, 25))
        out["energy_delta"] = maybe_signed64(rd) if rd is not None else None
        out["energy_after"] = pick_first(collect_varints(detail, 26), low=0, high=99)


def apply_damage_entry(out: Dict[str, Any], groups: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_DAMAGE fields and HP/damage sync hints."""
    out["kind"] = "damage"
    dmg_info = first_sub(groups.get(6, []))
    if dmg_info:
        out.update(_extract_skill_ref(dmg_info, skill_field=3))
        crit_vals = collect_varints(dmg_info, 5)
        out["is_critical"] = any(v != 0 for v in crit_vals) if crit_vals else None
        rt = pick_first(collect_varints(dmg_info, 7))
        out["restraint_type"] = maybe_signed64(rt) if rt is not None else None
        out["dam_type"] = pick_first(collect_varints(dmg_info, 9))

    dmg_sub = None
    hp_sub = None
    ir = first_sub(groups.get(12, []))
    if ir:
        for child in field_groups(ir).get(2, []):
            cs = child.get("sub")
            if cs is None:
                continue
            if pick_first(collect_varints(cs, 11)) is not None or pick_first(collect_varints(cs, 13)) is not None:
                dmg_sub = cs
            elif pick_first(collect_varints(cs, 3)) is not None:
                hp_sub = cs

    if dmg_sub:
        ro = pick_first(collect_varints(dmg_sub, 12))
        out["original_damage"] = _pick_sync_value(dmg_sub, 11, True)
        out["damage_change"] = _pick_sync_value(dmg_sub, 12, True)
        out["damage_result"] = _pick_sync_value(dmg_sub, 13, True)
        out["actual_damage"] = (
            out.get("original_damage")
            if out.get("original_damage") is not None
            else out.get("damage_result")
        )
        out["damage"] = out.get("actual_damage")
        out["overflow"] = maybe_signed64(ro) if ro is not None else None
        out["damage_target_side"] = pick_first(collect_varints(dmg_sub, 1))
        out["damage_target_side_name"] = side_name(out.get("damage_target_side"))

    if hp_sub:
        out["target_side"] = pick_first(collect_varints(hp_sub, 1)) or out.get("target_side")
        out["target_side_name"] = side_name(out.get("target_side"))
        out["hp_change"] = _pick_sync_value(hp_sub, 2, True)
        out["hp_result"] = _pick_sync_value(hp_sub, 3, True)
        out["target_hp_after"] = pick_first(collect_varints(hp_sub, 3), low=0, high=99999)


def apply_heal_entry(out: Dict[str, Any], groups: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_HEAL fields."""
    out["kind"] = "heal"
    hm = first_sub(groups.get(7, []))
    if hm:
        _extract_actor_target(hm, out)
        out["heal_type"] = pick_first(collect_varints(hm, 4))
        out["source_id"] = pick_first(collect_varints(hm, 3))
    ir = first_sub(groups.get(12, []))
    if ir:
        for child in field_groups(ir).get(2, []):
            cs = child.get("sub")
            if cs is None:
                continue
            hp = pick_first(collect_varints(cs, 3), low=0, high=99999)
            if hp is not None:
                out["target_hp_after"] = hp
                break


def apply_energy_entry(out: Dict[str, Any], groups: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_ENERGY fields."""
    out["kind"] = "energy"
    em = first_sub(groups.get(8, []))
    if em:
        _extract_actor_target(em, out)
        out["source_id"] = pick_first(collect_varints(em, 3))
    ir = first_sub(groups.get(12, []))
    if ir:
        for child in field_groups(ir).get(2, []):
            cs = child.get("sub")
            if cs is None:
                continue
            rd = pick_first(collect_varints(cs, 25))
            ea = pick_first(collect_varints(cs, 26), low=0, high=99)
            if rd is not None or ea is not None:
                out["energy_delta"] = maybe_signed64(rd) if rd is not None else None
                out["energy_after"] = ea
                break
