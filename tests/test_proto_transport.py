"""TGCP transport 解析模块的独立契约测试。"""
from __future__ import annotations

from src.protocol.proto.transport import (
    parse_record,
    parse_special_payload,
    parse_tgcp_control_packet,
    tgcp_command_name,
)
from src.protocol.proto_core import parse_record as compat_parse_record
from src.protocol.proto_core import parse_tgcp_control_packet as compat_parse_tgcp_control_packet
from tests.conftest import SESSION10_DIR
from tests.packet_reader import read_bin_packet


def test_transport_parse_record_matches_proto_core_facade_for_no_magic_c2s():
    pkt = read_bin_packet(SESSION10_DIR / "c2s_0x4013_0232_213443.139.bin")

    record = parse_record(pkt)

    assert record == compat_parse_record(pkt)
    assert record is not None
    assert record["transport_layout"] == "tgcp_4013_live_c2s_no_magic"
    assert record["opcode"] == 0x130B
    assert record["_decoded"]["req"][0]["cast_skill"]["skill_id"] == 716038000


def test_transport_control_packet_extracts_ack_session_key_and_matches_facade():
    key = b"1234567890abcdef"
    packet = {
        "cmd": 0x1002,
        "seq": 7,
        "direction": "s2c",
        "header_extra_hex": (b"\x00\x00" + key).hex(),
        "body_hex": b"ok".hex(),
    }

    record = parse_tgcp_control_packet(packet)

    assert record == compat_parse_tgcp_control_packet(packet)
    assert record["record_type"] == "tgcp_control"
    assert record["tgcp_command_name"] == "ACK"
    assert record["session_key_hex"] == key.hex()
    assert record["session_key_ascii"] == "1234567890abcdef"


def test_transport_command_name_and_special_payload_helpers():
    assert tgcp_command_name(0x4013) == "DATA"
    assert tgcp_command_name(0x7777) == "UNKNOWN_0x7777"

    special = parse_special_payload(0x013D, (123).to_bytes(8, "little") + (45).to_bytes(4, "little", signed=True))

    assert special == (
        "s2c_heartbeat_nty_binary",
        {"heartbeat_seq": 123, "server_logic_tick_ivl": 45},
    )

