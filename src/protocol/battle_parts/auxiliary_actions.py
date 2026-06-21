"""Handle and candidate-action auxiliary battle opcode extraction."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.protocol.proto_core import collect_varints, field_groups, pick_first


def extract_0220_handle(record: Dict[str, Any]) -> Optional[int]:
    """Extract handle value from opcode 0x0220."""
    root = record.get("root")
    if root is None:
        return None

    groups = field_groups(root)
    for entry in groups.get(2, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        handle = pick_first(collect_varints(sub, 1))
        if handle is not None:
            return handle
        for inner in field_groups(sub).get(2, []):
            inner_sub = inner.get("sub")
            if inner_sub is None:
                continue
            handle = pick_first(collect_varints(inner_sub, 1))
            if handle is not None:
                return handle

    return pick_first(collect_varints(root, 1))


def extract_01a9_action(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract action-candidate info from opcode 0x01A9."""
    out: Dict[str, Any] = {"candidate_ids": []}

    root = record.get("root")
    if root is None:
        return out

    for outer_entry in field_groups(root).get(4, []):
        outer = outer_entry.get("sub")
        if outer is None:
            continue
        payload_entry = next((entry for entry in field_groups(outer).get(2, []) if entry.get("sub")), None)
        if payload_entry is None:
            continue
        payload = payload_entry["sub"]
        ids: List[int] = []
        for field_no in (1, 2, 3):
            item = next((entry for entry in field_groups(payload).get(field_no, []) if entry.get("sub")), None)
            if item:
                for nested_field_no in (1, 2, 3):
                    ids.extend(collect_varints(item["sub"], nested_field_no))
        out.update({
            "candidate_ids": [int(value) for value in ids],
            "actor_token": pick_first(collect_varints(outer, 1)),
            "raw_kind": pick_first(collect_varints(outer, 4)),
        })
        if ids:
            out["primary_id"] = int(ids[0])
            break

    return out
