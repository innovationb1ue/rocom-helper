"""protobuf 底层解析模块的独立契约测试。"""
from __future__ import annotations

import struct

from src.protocol.proto import schema as proto_schema
from src.protocol.proto.tree import collect_varints, field_groups, first_text, walk_messages
from src.protocol.proto.wire import (
    maybe_signed64,
    normalize_c2s_opcode,
    parse_proto_message,
    read_varint,
    strip_tsf4g_padding,
    tsf4g_trailer_len,
)
from src.protocol.proto_core import decode_proto_by_schema as compat_decode_proto_by_schema
from src.protocol.proto_core import parse_proto_message as compat_parse_proto_message


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def test_parse_proto_message_decodes_wire_types_and_proto_core_compat():
    nested = bytes([0x08, 0x2A])
    data = b"".join(
        [
            bytes([0x08]), _varint(150),             # field 1 varint
            bytes([0x12, 0x06]), "你好".encode(),    # field 2 text
            bytes([0x1A, len(nested)]), nested,      # field 3 sub-message
            bytes([0x25]), struct.pack("<I", 7),    # field 4 fixed32
        ]
    )

    parsed = parse_proto_message(data)

    assert parsed == compat_parse_proto_message(data)
    assert parsed["clean"] is True
    assert collect_varints(parsed, 1) == [150]
    assert first_text(parsed, 2) == "你好"
    assert collect_varints(field_groups(parsed)[3][0]["sub"], 1) == [42]
    assert field_groups(parsed)[4][0]["u32le"] == 7
    assert [path for path, _ in walk_messages(parsed)] == ["root", "root.3[1]"]


def test_wire_helpers_keep_tgcp_padding_and_opcode_contracts():
    assert read_varint(_varint(300), 0) == (300, 2)
    assert normalize_c2s_opcode(0x0001130B) == (0x130B, True)
    assert normalize_c2s_opcode(0x130B) == (0x130B, False)
    assert maybe_signed64((1 << 64) - 2) == -2

    padded = b"payload" + b"tsf4g" + bytes([6])
    assert tsf4g_trailer_len(padded) == 6
    assert strip_tsf4g_padding(padded) == b"payload"


def test_schema_decode_is_independent_from_proto_core_facade(monkeypatch):
    monkeypatch.setattr(
        proto_schema,
        "_PROTO_SCHEMA_CACHE",
        {
            "messages": {
                "Demo": {
                    "fields": {
                        "1": {"name": "count", "type": "int32"},
                        "2": {"name": "enabled", "type": "bool"},
                        "3": {"name": "values", "type": "int32", "repeated": True},
                    }
                }
            }
        },
    )
    msg = {
        "fields": [
            {"field": 1, "wire": 0, "value": 9},
            {"field": 2, "wire": 0, "value": 1},
            {"field": 3, "wire": 2, "raw_hex": bytes([1, 2, 3]).hex()},
        ]
    }

    assert proto_schema.decode_proto_by_schema(msg, "Demo") == {
        "count": 9,
        "enabled": True,
        "values": [1, 2, 3],
    }
    assert compat_decode_proto_by_schema(msg, "Demo") == {
        "count": 9,
        "enabled": True,
        "values": [1, 2, 3],
    }

