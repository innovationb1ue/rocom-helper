"""基于 proto_schema.json 的可选 schema-aware decode。"""
from __future__ import annotations

import json
import logging
import struct
from typing import Any, Dict, List, Optional

from src.config import settings
from src.data.loader import get_opcode_pb_meta
from src.protocol.proto.tree import field_groups
from src.protocol.proto.wire import maybe_signed64, read_varint

logger = logging.getLogger(__name__)

_PROTO_SCHEMA_CACHE: Optional[Dict[str, Any]] = None


def load_proto_schema() -> Dict[str, Any]:
    """Lazy-load proto_schema.json for optional schema-aware post-processing."""
    global _PROTO_SCHEMA_CACHE
    if _PROTO_SCHEMA_CACHE is not None:
        return _PROTO_SCHEMA_CACHE
    path = settings.data_dir / "proto_schema.json"
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        logger.warning("Failed to load proto schema %s: %s", path, exc)
        data = {}
    _PROTO_SCHEMA_CACHE = data if isinstance(data, dict) else {}
    return _PROTO_SCHEMA_CACHE


def message_schema(message_name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not message_name:
        return None
    messages = load_proto_schema().get("messages", {})
    if not isinstance(messages, dict):
        return None
    for key in (message_name, f".Next.{message_name}", f"Next.{message_name}"):
        item = messages.get(key)
        if isinstance(item, dict):
            return item
    return None


def schema_fields(message_schema_data: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    fields = message_schema_data.get("fields", {})
    out: Dict[int, Dict[str, Any]] = {}
    if not isinstance(fields, dict):
        return out
    for key, value in fields.items():
        if not isinstance(value, dict):
            continue
        try:
            out[int(key)] = value
        except (TypeError, ValueError):
            continue
    return out


def decode_packed_numeric(blob: bytes, field_type: str) -> List[Any]:
    if field_type in {"float"}:
        return [
            round(float(struct.unpack("<f", blob[i:i + 4])[0]), 6)
            for i in range(0, len(blob) - (len(blob) % 4), 4)
        ]
    values: List[Any] = []
    off = 0
    while off < len(blob):
        try:
            raw, off = read_varint(blob, off)
        except ValueError:
            return []
        values.append(coerce_scalar(raw, field_type))
    return values


def coerce_scalar(value: int, field_type: str) -> Any:
    if field_type == "bool":
        return bool(value)
    if field_type in {"int32", "int64", "sint32", "sint64"}:
        return maybe_signed64(value)
    if field_type == "enum":
        return {"value": maybe_signed64(value), "name": None}
    return value


def decode_scalar_entry(entry: Dict[str, Any], field_type: str) -> Any:
    if entry.get("wire") == 5 and field_type == "float" and entry.get("raw_hex"):
        try:
            return round(float(struct.unpack("<f", bytes.fromhex(entry["raw_hex"]))[0]), 6)
        except (ValueError, struct.error):
            return None
    if entry.get("wire") == 2:
        if field_type in {"string"}:
            return entry.get("text")
        if field_type in {"bytes"}:
            return bytes.fromhex(entry.get("raw_hex", ""))
        raw = entry.get("raw_hex")
        if raw:
            packed = decode_packed_numeric(bytes.fromhex(raw), field_type)
            return packed if packed else None
    if "value" in entry:
        return coerce_scalar(entry["value"], field_type)
    return None


def decode_proto_by_schema(msg: Dict[str, Any], message_name: Optional[str]) -> Optional[Dict[str, Any]]:
    """Decode a parsed protobuf tree using proto_schema.json.

    The raw recursive tree remains the source of truth for fallback extractors; this
    helper only adds a named, schema-shaped view for semantic post-processing.
    """
    schema = message_schema(message_name)
    if schema is None:
        return None
    field_specs = schema_fields(schema)
    grouped = field_groups(msg)
    decoded: Dict[str, Any] = {}
    for field_no, entries in grouped.items():
        spec = field_specs.get(field_no)
        if spec is None:
            continue
        name = spec.get("name") or f"field_{field_no}"
        field_type = str(spec.get("type") or "")
        is_message = bool(spec.get("message"))
        repeated = bool(spec.get("repeated"))
        values: List[Any] = []
        for entry in entries:
            value: Any = None
            if is_message:
                sub = entry.get("sub")
                value = decode_proto_by_schema(sub, field_type) if sub is not None else None
            else:
                value = decode_scalar_entry(entry, field_type)
            if value is None:
                continue
            if repeated and isinstance(value, list) and not is_message and entry.get("wire") == 2:
                values.extend(value)
            else:
                values.append(value)
        if not values:
            continue
        decoded[name] = values if repeated or len(values) > 1 else values[0]
    return decoded


def attach_schema_decode(record: Dict[str, Any]) -> Dict[str, Any]:
    meta = get_opcode_pb_meta(record.get("opcode"))
    if not isinstance(meta, dict):
        return record
    message_name = meta.get("message")
    decoded = decode_proto_by_schema(record.get("root") or {}, message_name)
    if decoded is not None:
        record["_message_name"] = message_name
        record["_decoded"] = decoded
    return record

