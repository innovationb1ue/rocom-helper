"""Protobuf wire-format 原语与 TGCP 载荷小工具。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def read_varint(data: bytes, off: int) -> Tuple[int, int]:
    value = shift = 0
    cur = off
    while cur < len(data):
        byte = data[cur]
        cur += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, cur
        shift += 7
        if shift > 63:
            raise ValueError(f"varint too large at offset 0x{off:X}")
    raise ValueError(f"unterminated varint at offset 0x{off:X}")


def maybe_utf8(blob: bytes) -> Optional[str]:
    if not blob:
        return None
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return None if any(ord(c) < 0x20 and c not in "\r\n\t" for c in text) else text


def strip_tsf4g_padding(data: bytes) -> bytes:
    marker = b"tsf4g"
    if data.rfind(marker) == len(data) - 6:
        pad = data[-1]
        if len(marker) + 1 <= pad <= 64 and len(data) >= pad:
            return data[:-pad]
        if pad == 1:
            return data[:-1]
        if 0 < pad <= 16 and len(data) >= pad and all(b == pad for b in data[-pad:]):
            return data[:-pad]
    return data


def tsf4g_trailer_len(data: bytes) -> int:
    marker = b"tsf4g"
    if data.rfind(marker) != len(data) - 6:
        return 0
    pad = data[-1]
    if len(marker) + 1 <= pad <= 64 and len(data) >= pad:
        return pad
    if pad == 1:
        return 1
    if 0 < pad <= 16 and len(data) >= pad and all(b == pad for b in data[-pad:]):
        return pad
    return 0


def normalize_c2s_opcode(opcode: int) -> Tuple[int, bool]:
    low16 = opcode & 0xFFFF
    if opcode > 0xFFFF and (opcode >> 16) == 0x0001 and low16:
        return low16, True
    return opcode, False


def maybe_signed64(value: int) -> int:
    return value - (1 << 64) if value >= (1 << 63) else value


def parse_proto_message(
    data: bytes,
    *,
    depth: int = 0,
    max_depth: int = 10,
    max_fields: int = 5000,
) -> Dict[str, Any]:
    """递归解析 protobuf wire tree，保留原始字段号和 wire type。"""
    fields: List[Dict[str, Any]] = []
    off, clean = 0, True
    while off < len(data):
        if len(fields) >= max_fields:
            clean = False
            break
        start = off
        try:
            tag, off = read_varint(data, off)
        except ValueError:
            clean = False
            break
        field_no, wire_type = tag >> 3, tag & 7
        entry: Dict[str, Any] = {"field": field_no, "wire": wire_type, "offset": start}
        try:
            if wire_type == 0:
                entry["value"], off = read_varint(data, off)
            elif wire_type == 1:
                if off + 8 > len(data):
                    clean = False
                    break
                entry["raw_hex"] = data[off:off + 8].hex()
                off += 8
            elif wire_type == 2:
                blen, off = read_varint(data, off)
                if off + blen > len(data):
                    clean = False
                    break
                blob = data[off:off + blen]
                off += blen
                entry["len"] = blen
                entry["raw_hex"] = blob.hex()
                text = maybe_utf8(blob)
                if text is not None:
                    entry["text"] = text
                elif depth < max_depth and blob:
                    sub = parse_proto_message(
                        blob,
                        depth=depth + 1,
                        max_depth=max_depth,
                        max_fields=max_fields,
                    )
                    if sub["fields"] and sub["consumed"] == len(blob):
                        entry["sub"] = sub
            elif wire_type == 5:
                if off + 4 > len(data):
                    clean = False
                    break
                blob = data[off:off + 4]
                off += 4
                entry["raw_hex"] = blob.hex()
                entry["u32le"] = int.from_bytes(blob, "little")
            else:
                clean = False
                break
        except ValueError:
            clean = False
            break
        fields.append(entry)
    return {"fields": fields, "consumed": off, "clean": clean and off == len(data)}

