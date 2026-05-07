"""Tests for summarize() opcode dispatch and PB map fallback."""
from __future__ import annotations

import pytest
from pathlib import Path

from src.protocol.opcodes import summarize
from src.protocol.proto_core import parse_record, extract_inner_message
from tests.packet_reader import read_bin_packet, BATTLE_OPCODES

SESSION_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"


def _load_one_packet(filename: str):
    path = SESSION_DIR / filename
    if not path.exists():
        pytest.skip(f"{filename} not found")
    pkt = read_bin_packet(path)
    return parse_record(pkt)


class TestSummarizeRegisteredOpcodes:
    """Registered battle opcodes with real parsed records should return their dedicated kind."""

    def test_battle_enter(self):
        record = _load_one_packet("s2c_0x4013_1599_212333.620.bin")
        kind, _ = summarize(record)
        assert kind == "battle_enter"

    def test_skill_declare(self):
        record = _load_one_packet("s2c_0x4013_1620_212353.251.bin")
        kind, _ = summarize(record)
        assert kind == "server_skill_declare"


class TestSummarizePbMapFallback:
    """Opcodes not in _OPCODE_REGISTRY but in opcode_pb_map.json return the message name."""

    def test_login_req(self):
        kind, summary = summarize({"opcode": 257})  # 0x0101
        assert kind == "ZoneLoginReq"
        assert summary.get("pb_type") == "Req"

    def test_heartbeat(self):
        kind, _ = summarize({"opcode": 289})  # 0x0121
        assert kind == "ZoneHeartbeatReq"

    def test_scene_move(self):
        kind, _ = summarize({"opcode": 307})  # 0x0133
        assert kind == "ZoneSceneMoveReq"

    def test_bag_req(self):
        kind, _ = summarize({"opcode": 353})  # 0x0161
        assert kind == "ZoneGetBagReq"

    def test_battle_load_req(self):
        kind, _ = summarize({"opcode": 0x1305})
        assert kind == "ZoneBattleLoadFinishReq"

    def test_battle_emoji_req(self):
        kind, _ = summarize({"opcode": 0x1331})
        assert kind == "ZoneBattleEmojiReq"


class TestSummarizeUnknown:
    """Opcodes not in any mapping return 'unknown'."""

    def test_truly_unknown(self):
        kind, summary = summarize({"opcode": 0xEEEE})
        assert kind == "unknown"
        assert summary["opcode"] == 0xEEEE


class TestSummarizeAllSessionOpcodes:
    """Every opcode in the captured session should resolve to a non-'unknown' kind (except truly unmapped)."""

    def test_no_unknown_in_session(self):
        unknown = []
        for fpath in sorted(SESSION_DIR.glob("*0x4013*.bin")):
            pkt = read_bin_packet(fpath)
            if not pkt["decrypted_body_hex"]:
                continue
            record = parse_record(pkt)
            if record is None:
                continue
            opcode = record.get("opcode", 0)
            inner = extract_inner_message(record.get("root", {})) if opcode == 0x0414 else None
            kind, _ = summarize(record, inner)
            if kind == "unknown":
                unknown.append((fpath.name, hex(opcode)))
        # Allow a few truly unmapped opcodes
        assert len(unknown) <= 5, f"Too many unknown opcodes: {unknown}"
