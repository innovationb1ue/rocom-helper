"""Creature and metadata auxiliary battle opcode extraction."""
from __future__ import annotations

from typing import Any, Dict, List

from src.protocol.proto_core import (
    collect_varints,
    extract_creature,
    field_groups,
    first_text,
    parse_proto_message,
    pick_first,
    read_varint,
)


def extract_0102_creatures(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract creature list from opcode 0x0102 using RKPP's root.2[*].4[*] path."""
    root = record.get("root")
    if root is None:
        return []

    out: List[Dict[str, Any]] = []
    for outer in field_groups(root).get(2, []):
        os_ = outer.get("sub")
        if os_ is None:
            continue
        for re_ in field_groups(os_).get(4, []):
            rh = re_.get("raw_hex")
            if not rh:
                continue
            blob = bytes.fromhex(rh)
            off = 0
            while off < len(blob):
                try:
                    tag, off = read_varint(blob, off)
                    length, off = read_varint(blob, off)
                except ValueError:
                    break
                fn, wt = tag >> 3, tag & 7
                if fn != 1 or wt != 2 or off + length > len(blob):
                    break
                eb = blob[off:off + length]
                off += length
                creature = extract_creature(
                    parse_proto_message(eb),
                    path="root.2[*].4[*].1[*]",
                    record=record,
                )
                if creature and creature.get("slot") not in (None, 0):
                    out.append(creature)

    dedup: Dict[int, Dict[str, Any]] = {}
    for creature in out:
        slot = creature.get("slot")
        if slot is not None:
            dedup[int(slot)] = creature
    return [dedup[slot] for slot in sorted(dedup)]


def extract_0102_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract player metadata from opcode 0x0102."""
    root = record.get("root")
    if root is None:
        return {}

    groups = field_groups(root)
    out: Dict[str, Any] = {}

    for entry in groups.get(1, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        user_id = pick_first(collect_varints(sub, 1))
        uin = pick_first(collect_varints(sub, 2))
        nickname = first_text(sub, 3)
        if user_id is not None:
            out["user_id"] = user_id
        if uin is not None:
            out["uin"] = uin
        if nickname is not None:
            out["nickname"] = nickname

    for entry in groups.get(3, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        pet_ids = collect_varints(sub, 1)
        active_pet_id = pick_first(collect_varints(sub, 2))
        if pet_ids:
            out["pet_ids"] = pet_ids
        if active_pet_id is not None:
            out["active_pet_id"] = active_pet_id

    return out
