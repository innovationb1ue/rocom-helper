"""Opcode summarize dispatch helpers."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from src.protocol.opcode_registry import OpcodeRegistry

PbMetaLoader = Callable[[int], Optional[Dict[str, Any]]]


def opcode_from_record(record: Any) -> int:
    """Resolve an opcode from an int-like value, mapping, or parsed record object."""
    if hasattr(record, "opcode"):
        return int(record.opcode)
    if isinstance(record, dict):
        return int(record.get("opcode", 0))
    return int(record)


def inner_message_id(inner: Any) -> int:
    """Resolve an inner message id from a mapping or object."""
    if isinstance(inner, dict):
        return int(inner.get("message_id", -1))
    return int(getattr(inner, "message_id", -1))


def summarize_record(
    record: Any,
    inner: Optional[Any],
    *,
    opcode_registry: OpcodeRegistry,
    inner_registry: OpcodeRegistry,
    pb_meta_loader: Optional[PbMetaLoader] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Dispatch a parsed record through registered opcode handlers and PB fallback."""
    opcode = opcode_from_record(record)

    if opcode == 0x0414 and inner is not None:
        entry = inner_registry.get(inner_message_id(inner))
        if entry is not None:
            kind, handler = entry
            return kind, handler(record, inner)

    entry = opcode_registry.get(opcode)
    if entry is not None:
        kind, handler = entry
        return kind, handler(record, inner)

    if pb_meta_loader is None:
        from src.data.loader import get_opcode_pb_meta

        pb_meta_loader = get_opcode_pb_meta

    meta = pb_meta_loader(opcode)
    if meta is not None:
        message = meta.get("message", "")
        return message if message else "unknown", {
            "opcode": opcode,
            "pb_type": meta.get("type", ""),
        }

    return "unknown", {"opcode": opcode}
