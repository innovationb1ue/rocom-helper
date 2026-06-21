"""Generic perform entry fallback extraction."""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.protocol.proto_core import (
    _extract_actor_target,
    collect_varints,
    field_groups,
    first_sub,
    maybe_signed64,
    pick_first,
)


PERFORM_SCHEMA_FIELD_BY_TYPE = {
    14: (19, "use_item"),
    16: (21, "monster_catch_change"),
    17: (22, "monster_escape_change"),
    18: (23, "catch_pet_info"),
    20: (25, "pet_evolution"),
    21: (28, "skill_aura"),
    26: (31, "special_perform"),
    27: (35, "cheers_switch"),
    28: (36, "pet_escape"),
    31: (40, "cmd_failed"),
    32: (41, "battler_escape"),
    33: (42, "battler_heal"),
    36: (48, "runaway"),
    40: (49, "prepare_to_battle"),
    41: (50, "bag_to_prepare"),
    42: (51, "feature_resonance"),
    43: (52, "box_shield_break"),
}


def raw_subfield_values(msg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a compact raw field dump for simple perform payloads."""
    if msg is None:
        return {}
    out: Dict[str, Any] = {}
    for field_no, entries in field_groups(msg).items():
        values = [maybe_signed64(e["value"]) for e in entries if "value" in e]
        if values:
            out[f"field_{field_no}"] = values if len(values) > 1 else values[0]
        texts = [e["text"] for e in entries if e.get("text")]
        if texts:
            out[f"field_{field_no}_text"] = texts if len(texts) > 1 else texts[0]
    return out


def apply_generic_perform_entry(
    out: Dict[str, Any],
    entry_type: Optional[int],
    sub: Dict[str, Any],
) -> None:
    """Populate ``out`` for schema-mapped or unknown perform entry types."""
    schema_info = PERFORM_SCHEMA_FIELD_BY_TYPE.get(entry_type)
    if schema_info is None:
        out["kind"] = "unhandled_battle_perform"
        out["perform_type"] = entry_type
        out["raw_fields"] = raw_subfield_values(sub)
        return

    field_no, kind = schema_info
    out["kind"] = kind
    out["schema_field"] = field_no
    payload = first_sub(field_groups(sub).get(field_no, []))
    if payload is None:
        return

    out.update(raw_subfield_values(payload))
    if kind == "cmd_failed":
        out["failed_reason"] = pick_first(collect_varints(payload, 1))
    elif kind == "battler_escape":
        _extract_actor_target(payload, out)
    elif kind == "battler_heal":
        _extract_actor_target(payload, out)
        out["heal_value"] = pick_first(collect_varints(payload, 3))
    elif kind == "runaway":
        _extract_actor_target(payload, out)
    elif kind == "use_item":
        out["caster_id"] = pick_first(collect_varints(payload, 1))
        out["target_id"] = pick_first(collect_varints(payload, 2))
        out["item_id"] = pick_first(collect_varints(payload, 3))
