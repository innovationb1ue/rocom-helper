"""TGCP DATA/control 记录解析。"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from src.data.loader import get_opcode_pb_meta
from src.protocol.proto.schema import attach_schema_decode
from src.protocol.proto.wire import (
    normalize_c2s_opcode,
    parse_proto_message,
    strip_tsf4g_padding,
    tsf4g_trailer_len,
)

TGCP_COMMAND_NAMES: Dict[int, str] = {
    0x1001: "SYN", 0x1002: "ACK", 0x2001: "AUTH_REQ", 0x2002: "AUTH_RSP",
    0x4013: "DATA", 0x5002: "SSTOP", 0x6002: "BINGO", 0x9001: "HEARTBEAT",
}
SSTOP_CODE_NAMES: Dict[int, str] = {0x11: "AUTH_INVALID", 0x12: "AUTH_REQUIRED"}


def tgcp_command_name(cmd: int) -> str:
    return TGCP_COMMAND_NAMES.get(cmd, f"UNKNOWN_0x{cmd:04X}")


def parse_special_payload(opcode: int, payload: bytes) -> Optional[Tuple[str, Dict[str, Any]]]:
    if opcode == 0x013D and len(payload) == 12:
        return "s2c_heartbeat_nty_binary", {
            "heartbeat_seq": int.from_bytes(payload[0:8], "little"),
            "server_logic_tick_ivl": int.from_bytes(payload[8:12], "little", signed=True),
        }
    if opcode == 0x013F and len(payload) == 40:
        return "s2c_heartbeat_result_binary", {
            "ret_info": {"ret_code": int.from_bytes(payload[0:4], "little")},
            "heartbeat_seq": int.from_bytes(payload[4:12], "little"),
            "server_time": int.from_bytes(payload[12:20], "little"),
        }
    return None


def _build_payload_root(opcode: int, payload: bytes) -> Tuple[Dict[str, Any], str, Optional[Dict[str, Any]]]:
    special = parse_special_payload(opcode, payload)
    if special:
        return {"fields": [], "consumed": len(payload), "clean": True}, special[0], special[1]
    if not payload:
        return {"fields": [], "consumed": 0, "clean": True}, "protobuf", None
    return parse_proto_message(payload), "protobuf", None


def _empty_root() -> Dict[str, Any]:
    return {"fields": [], "consumed": 0, "clean": True}


def _is_probable_business_opcode(opcode: int) -> bool:
    return isinstance(opcode, int) and get_opcode_pb_meta(opcode) is not None


def _finalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return attach_schema_decode(record)


def _parse_record_v14(body: bytes, common: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if len(body) < 0x1E or body[4:6] != b"\x55\xaa" or body[24:26] != b"\x39\x63":
        return None
    reserved = int.from_bytes(body[10:12], "big")
    version = int.from_bytes(body[12:16], "big")
    record_len = int.from_bytes(body[6:10], "big")
    raw_payload = body[30:]
    trailer_len = tsf4g_trailer_len(raw_payload)
    no_trailer_len = len(body) - trailer_len
    if reserved != 0 or version not in {0, 1} or record_len != no_trailer_len - 4:
        return None
    transport_seq = int.from_bytes(body[0:4], "big")
    session_id = int.from_bytes(body[16:20], "big")
    sub_id = int.from_bytes(body[20:24], "big")
    req_seq = int.from_bytes(body[26:30], "big")
    payload = strip_tsf4g_padding(raw_payload)
    if common["direction"] == "c2s":
        raw_opcode = sub_id
        opcode, normalized = normalize_c2s_opcode(raw_opcode)
    else:
        raw_opcode = session_id
        opcode = session_id & 0xFFFF
        normalized = False
    root, _, _ = _build_payload_root(opcode, payload)
    return _finalize_record({
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_v14", "transport_seq": transport_seq,
        "record_len": record_len, "session_id": session_id,
        "session_id_hex": f"0x{session_id:08X}", "sub_id": sub_id,
        "sub_id_hex": f"0x{sub_id:08X}", "opcode": opcode,
        "opcode_hex": f"0x{opcode:04X}", "raw_opcode": raw_opcode,
        "raw_opcode_hex": f"0x{raw_opcode:08X}", "opcode_normalized": normalized,
        "req_seq": req_seq, "payload_len": len(payload),
        "payload_trailer_len": trailer_len, "root": root,
    })


def _parse_record_live_s2c(body: bytes, common: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if common["direction"] != "s2c" or len(body) < 10 or body[4:6] != b"\x55\xaa":
        return None
    opcode = int.from_bytes(body[0:4], "big")
    if not (0 < opcode <= 0xFFFF):
        return None
    subtype = int.from_bytes(body[6:10], "big")
    raw_payload = body[10:]
    trailer_len = tsf4g_trailer_len(raw_payload)
    payload = strip_tsf4g_padding(raw_payload)
    root, _, _ = _build_payload_root(opcode, payload)
    return _finalize_record({
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_live_s2c", "opcode": opcode,
        "opcode_hex": f"0x{opcode:04X}", "subtype": subtype,
        "payload_len": len(payload), "payload_trailer_len": trailer_len, "root": root,
    })


def _parse_record_live_c2s(body: bytes, common: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if common["direction"] != "c2s" or len(body) < 14 or body[8:10] != b"\x39\x63":
        return None
    raw_opcode = int.from_bytes(body[4:8], "big")
    if not (raw_opcode >> 16 in {0x0000, 0x0001} and (raw_opcode & 0xFFFF) != 0):
        return None
    opcode, normalized = normalize_c2s_opcode(raw_opcode)
    req_seq = int.from_bytes(body[10:14], "big")
    raw_payload = body[14:]
    trailer_len = tsf4g_trailer_len(raw_payload)
    payload = strip_tsf4g_padding(raw_payload)
    root, _, _ = _build_payload_root(opcode, payload)
    return _finalize_record({
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_live_c2s",
        "opcode": opcode, "opcode_hex": f"0x{opcode:04X}",
        "raw_opcode": raw_opcode, "raw_opcode_hex": f"0x{raw_opcode:08X}",
        "opcode_normalized": normalized, "req_seq": req_seq,
        "payload_len": len(payload), "payload_trailer_len": trailer_len, "root": root,
    })


def _parse_record_live_c2s_no_magic(body: bytes, common: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse observed c2s business packets that omit the 0x3963 marker."""
    if common["direction"] != "c2s" or len(body) < 14 or body[8:10] == b"\x39\x63":
        return None
    prefix_u32 = int.from_bytes(body[0:4], "big")
    raw_opcode = int.from_bytes(body[4:8], "big")
    opcode, normalized = normalize_c2s_opcode(raw_opcode)
    if not _is_probable_business_opcode(opcode):
        return None
    req_seq = int.from_bytes(body[10:14], "big")
    raw_payload = body[14:]
    trailer_len = tsf4g_trailer_len(raw_payload)
    payload = strip_tsf4g_padding(raw_payload)
    root, _, _ = _build_payload_root(opcode, payload)
    if not root.get("clean"):
        return None
    if any(entry.get("field") == 0 for entry in root.get("fields", [])):
        return None
    return _finalize_record({
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_live_c2s_no_magic",
        "transport_seq": prefix_u32, "prefix_u32": prefix_u32,
        "prefix_u32_hex": f"0x{prefix_u32:08X}",
        "opcode": opcode, "opcode_hex": f"0x{opcode:04X}",
        "raw_opcode": raw_opcode, "raw_opcode_hex": f"0x{raw_opcode:08X}",
        "opcode_normalized": normalized,
        "marker_u16": int.from_bytes(body[8:10], "big"),
        "marker_u16_hex": f"0x{int.from_bytes(body[8:10], 'big'):04X}",
        "req_seq": req_seq,
        "payload_len": len(payload), "payload_trailer_len": trailer_len,
        "root": root,
    })


def _parse_record_live_c2s_short_heartbeat(body: bytes, common: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if common["direction"] != "c2s" or len(body) < 16 or body.find(b"tsf4g", 8) < 0:
        return None
    opcode = int.from_bytes(body[6:8], "big")
    if opcode != 0x013E:
        return None
    req_seq = int.from_bytes(body[14:16], "little")
    leading_u32 = int.from_bytes(body[0:4], "big")
    return _finalize_record({
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_live_c2s_short_heartbeat",
        "transport_seq": leading_u32, "prefix_u32": leading_u32,
        "prefix_u32_hex": f"0x{leading_u32:08X}",
        "opcode": opcode, "opcode_hex": f"0x{opcode:04X}",
        "format": "c2s_short_heartbeat", "req_seq": req_seq,
        "payload_len": 0, "root": _empty_root(),
    })


def parse_record(packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse a decrypted TGCP DATA packet into a normalized business record."""
    if packet.get("cmd") != 0x4013 or not packet.get("decrypted_body_hex"):
        return None
    body = bytes.fromhex(packet["decrypted_body_hex"])
    common = {"seq": packet["seq"], "direction": packet["direction"],
              "first_frame": packet.get("first_frame"), "first_time": packet.get("first_time")}
    return (_parse_record_v14(body, common)
            or _parse_record_live_s2c(body, common)
            or _parse_record_live_c2s(body, common)
            or _parse_record_live_c2s_no_magic(body, common)
            or _parse_record_live_c2s_short_heartbeat(body, common))


def parse_tgcp_control_packet(packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cmd = int(packet.get("cmd", 0) or 0)
    if cmd == 0x4013:
        return None
    header_extra = bytes.fromhex(packet.get("header_extra_hex") or "")
    body = bytes.fromhex(packet.get("body_hex") or "")
    record: Dict[str, Any] = {
        "record_type": "tgcp_control", "transport_kind": "tgcp_control",
        "transport_layout": "be21_control", "seq": packet.get("seq"),
        "direction": packet.get("direction"), "cmd": cmd,
        "cmd_hex": f"0x{cmd:04X}", "tgcp_command_name": tgcp_command_name(cmd),
        "body_len": len(body),
    }
    if cmd == 0x1002 and len(header_extra) >= 18:
        key = header_extra[2:18]
        record["session_key_hex"] = key.hex()
        if all(32 <= b < 127 for b in key):
            record["session_key_ascii"] = key.decode("ascii", errors="ignore")
    return record

