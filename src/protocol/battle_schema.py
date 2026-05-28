"""Schema-first 提取辅助函数。

``protocol.battle`` 负责公开 opcode 提取函数；本模块只放与 schema/raw
形态切换相关的纯工具，降低战斗协议门面里的混杂职责。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.protocol.proto_core import field_groups


def _schema_payload(record: Dict[str, Any], expected_message: str) -> Optional[Dict[str, Any]]:
    decoded = record.get("_decoded")
    if isinstance(decoded, dict) and decoded:
        message_name = record.get("_message_name")
        if message_name in (None, "", expected_message):
            return decoded
    return None


def _enum_value(value: Any) -> Optional[int]:
    if isinstance(value, dict):
        return _enum_value(value.get("value"))
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return None


def _enum_name(value: Any) -> Optional[str]:
    return value.get("name") if isinstance(value, dict) and isinstance(value.get("name"), str) else None


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _first_value(value: Any) -> Any:
    items = _as_list(value)
    return items[0] if items else None


def _schema_quality(
    detail: Dict[str, Any],
    *,
    message: str,
    found: bool,
    level: str = "battle_semantic",
) -> Dict[str, Any]:
    detail.update({
        "schema_message": message,
        "schema_found": found,
        "parse_quality": "schema_postprocess" if found else "raw_field_postprocess",
        "semantic_level": level,
    })
    return detail


def _compact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None and v != [] and v != {}}


def _schema_or_raw(record: Dict[str, Any], message_name: str) -> Dict[str, Any]:
    """简单通知类 opcode 的统一解析：schema 存在时用 schema，否则用紧凑 raw 字段。"""
    decoded = _schema_payload(record, message_name)
    if decoded is not None:
        return dict(decoded)
    root = record.get("root")
    if root is None:
        return {}
    out: Dict[str, Any] = {}
    for fn, entries in field_groups(root).items():
        vals = [
            entry.get("varint")
            for entry in entries
            if isinstance(entry, dict) and entry.get("varint") is not None
        ]
        if vals:
            out[f"field_{fn}"] = vals[0] if len(vals) == 1 else vals
        for entry in entries:
            if entry.get("text"):
                out[f"field_{fn}_text"] = entry["text"]
                break
    return out


def _make_simple_extractor(message_name: str):
    def _extract(record: Dict[str, Any]) -> Dict[str, Any]:
        detail = _schema_or_raw(record, message_name)
        detail["opcode"] = record.get("opcode")
        detail["opcode_hex"] = record.get("opcode_hex", "")
        return detail

    return _extract


def _raw_field_dump(record: Dict[str, Any]) -> Dict[str, Any]:
    """通用 raw 字段转储，提取所有 varint 字段。"""
    root = record.get("root")
    detail: Dict[str, Any] = {}
    if root is not None:
        for fn, entries in field_groups(root).items():
            vals = [
                entry.get("varint")
                for entry in entries
                if isinstance(entry, dict) and entry.get("varint") is not None
            ]
            if vals:
                detail[f"field_{fn}"] = vals[0] if len(vals) == 1 else vals
    detail["opcode"] = record.get("opcode")
    detail["opcode_hex"] = record.get("opcode_hex", "")
    return detail
