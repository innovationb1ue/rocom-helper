"""Skill command opcode extraction for battle protocol."""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.protocol.proto_core import (
    _attach_skill_meta,
    collect_varints,
    normalize_skill_id,
    pick_first,
    side_name,
    skill_name,
)
from src.protocol.battle_actions import _extract_skill_or_special
from src.protocol.battle_schema import (
    _as_list,
    _compact_dict,
    _enum_value,
    _schema_payload,
    _schema_quality,
)


def extract_130b_skill_select(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract skill-selection details from opcode 0x130B."""
    root = record.get("root")
    if root is None:
        return None

    decoded = _schema_payload(record, "ZoneBattleCmdPushbackReq")
    if decoded is not None:
        req_items = _as_list(decoded.get("req"))
        first_req = next((item for item in req_items if isinstance(item, dict)), {})
        cast_skill = first_req.get("cast_skill") if isinstance(first_req.get("cast_skill"), dict) else {}
        change_pet = first_req.get("change_pet") if isinstance(first_req.get("change_pet"), dict) else {}
        use_item = first_req.get("use_item") if isinstance(first_req.get("use_item"), dict) else {}
        skill_raw = _enum_value(cast_skill.get("skill_id")) if cast_skill else None
        sid = normalize_skill_id(skill_raw)
        out = _compact_dict({
            "cmd_slot": _enum_value(decoded.get("wl_req_id")),
            "cmd_flag": _enum_value(decoded.get("req_type")),
            "actor_side": _enum_value(cast_skill.get("caster_pet_id")) if cast_skill else None,
            "actor_side_name": side_name(_enum_value(cast_skill.get("caster_pet_id"))) if cast_skill else None,
            "target_side": _enum_value(cast_skill.get("target_pet_id")) if cast_skill else None,
            "target_side_name": side_name(_enum_value(cast_skill.get("target_pet_id"))) if cast_skill else None,
            "target_pet_pos": _enum_value(cast_skill.get("target_pet_pos")) if cast_skill else None,
            "skill_id_x100": skill_raw,
            "skill_id": sid,
            "skill_name": skill_name(sid),
            "change_pet_id": _enum_value(change_pet.get("pet_id")) if change_pet else None,
            "item_id": _enum_value(use_item.get("item_id")) if use_item else None,
            "opcode": record.get("opcode"),
            "opcode_hex": record.get("opcode_hex", ""),
        })
        if sid:
            _attach_skill_meta(out, sid)
        out["extract_kind"] = "skill_select"
        _schema_quality(out, message="ZoneBattleCmdPushbackReq", found=True)
        return out

    cmd_slot = pick_first(collect_varints(root, 5))
    cmd_flag = pick_first(collect_varints(root, 1))

    result = _extract_skill_or_special(
        record,
        extra_fields={
            "cmd_slot": cmd_slot,
            "cmd_flag": cmd_flag,
        },
        command_flag=cmd_flag,
        command_slot=cmd_slot,
    )
    if result is not None:
        result["extract_kind"] = "skill_select"
    return result


def extract_1322_skill_declare(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract skill-declaration details from opcode 0x1322."""
    root = record.get("root")
    if root is None:
        return None

    battle_token = pick_first(collect_varints(root, 1))
    result = _extract_skill_or_special(
        record,
        extra_fields={"battle_token": battle_token},
    )
    if result is not None:
        result["extract_kind"] = "skill_declare"
    return result
