"""Refresh and energy command extraction for battle protocol."""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.protocol.proto_core import (
    _ENERGY_BOTTLE_MAX,
    collect_varints,
    field_groups,
    first_sub,
    maybe_signed64,
    normalize_skill_id,
    pick_first,
    skill_name,
)


def extract_13f4_refresh(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract refresh / energy info from opcode 0x13F4."""
    root = record.get("root")
    if root is None:
        return None

    container = first_sub(field_groups(root).get(1, []))
    if container is None:
        return None

    cg = field_groups(container)
    detail: Dict[str, Any] = {
        "packet_state": pick_first(collect_varints(container, 1)),
        "packet_phase": pick_first(collect_varints(container, 3)),
        "packet_index": pick_first(collect_varints(container, 5)),
        "skill_options": [],
    }

    for entry in cg.get(2, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        et = pick_first(collect_varints(sub, 1))

        if et == 14:
            _extract_skill_options(sub, detail)
        elif et == 6:
            _extract_energy_refresh(sub, detail)

    detail["skill_options"].sort(
        key=lambda it: (it.get("slot") is None, int(it.get("slot") or 0), int(it.get("skill_id") or 0))
    )

    if not detail["skill_options"] and detail.get("energy_delta") is None and detail.get("energy_after") is None:
        return None

    if detail.get("energy_after") == _ENERGY_BOTTLE_MAX and (detail.get("energy_delta") or 0) > 0:
        detail["action_name"] = "能量瓶"
        detail["kind"] = "energy_bottle"

    detail["opcode"] = record.get("opcode")
    detail["opcode_hex"] = record.get("opcode_hex", "")
    return detail


def _extract_skill_options(entry: Dict[str, Any], detail: Dict[str, Any]) -> None:
    meta = first_sub(field_groups(entry).get(19, []))
    if meta:
        detail["battle_token"] = pick_first(collect_varints(meta, 1), low=100_000)
        for i in range(2, 6):
            detail[f"arg{i}"] = pick_first(collect_varints(meta, i))
    options_root = first_sub(field_groups(entry).get(12, []))
    if not options_root:
        return
    for skill_entry in field_groups(options_root).get(3, []):
        skill_msg = skill_entry.get("sub")
        if not skill_msg:
            continue
        skill_raw = pick_first(collect_varints(skill_msg, 2), low=100_000)
        sid = normalize_skill_id(skill_raw)
        if sid:
            detail["skill_options"].append({
                "skill_id_x100": skill_raw,
                "skill_id": sid,
                "skill_name": skill_name(sid),
                "slot": pick_first(collect_varints(skill_msg, 10), low=0, high=20),
            })


def _extract_energy_refresh(entry: Dict[str, Any], detail: Dict[str, Any]) -> None:
    item_root = first_sub(field_groups(entry).get(12, []))
    info = first_sub(field_groups(item_root).get(2, [])) if item_root else None
    if not info:
        return
    raw_delta = pick_first(collect_varints(info, 25))
    detail["energy_delta"] = maybe_signed64(raw_delta) if raw_delta is not None else None
    detail["energy_after"] = pick_first(collect_varints(info, 26), low=0, high=99)
