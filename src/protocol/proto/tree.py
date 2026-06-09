"""解析后 protobuf tree 的遍历和字段查询工具。"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


def walk_messages(msg: Dict[str, Any], path: str = "root") -> List[Tuple[str, Dict[str, Any]]]:
    out = [(path, msg)]
    per_field: Dict[int, int] = defaultdict(int)
    for entry in msg["fields"]:
        sub = entry.get("sub")
        if sub is None:
            continue
        per_field[entry["field"]] += 1
        out.extend(walk_messages(sub, f"{path}.{entry['field']}[{per_field[entry['field']]}]"))
    return out


def field_groups(msg: Optional[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    if msg is None:
        return {}
    cached = msg.get("_groups")
    if isinstance(cached, dict):
        return cached
    grouped: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for entry in msg["fields"]:
        grouped[entry["field"]].append(entry)
    cached = dict(grouped)
    msg["_groups"] = cached
    return cached


def collect_varints(msg: Optional[Dict[str, Any]], field_no: int) -> List[int]:
    return [e["value"] for e in field_groups(msg).get(field_no, []) if "value" in e]


def first_text(msg: Dict[str, Any], field_no: int) -> Optional[str]:
    for e in field_groups(msg).get(field_no, []):
        if e.get("text"):
            return e["text"]
    return None


def first_sub(entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return next((e["sub"] for e in entries if e.get("sub") is not None), None)


def pick_first(values: List[int], *, low: Optional[int] = None, high: Optional[int] = None) -> Optional[int]:
    for v in values:
        if (low is None or v >= low) and (high is None or v <= high):
            return v
    return None

