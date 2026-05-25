"""parse_record 单元测试 — 验证 TGCP DATA 包解析逻辑。"""
from __future__ import annotations

import pytest
from src.protocol.proto_core import parse_record


class TestParseRecordReturnsNone:
    """parse_record 对未知格式返回 None — 不应触发 parse_fail 事件。"""

    def test_unknown_c2s_format_returns_none(self):
        """224B c2s 包 body 不匹配任何已知格式 → 返回 None（c2s benign）。"""
        fake_body = bytes(224)
        pkt = {
            "cmd": 0x4013,
            "direction": "c2s",
            "seq": 9999,
            "decrypted_body_hex": fake_body.hex(),
        }
        result = parse_record(pkt)
        assert result is None

    def test_malformed_v14_c2s_returns_none(self):
        """c2s 方向传了 v14 格式（magic 不匹配） → 返回 None。"""
        # v14 magic at [4:6] must be 0x55AA, c2s body[8:10] must be 0x3963
        # Build body that is 30+ bytes but has wrong magic for c2s path
        body = bytearray(30 + 200)
        body[4:6] = b"\xFF\xFF"  # not 0x55AA → v14 fails
        body[8:10] = b"\xFF\xFF"  # not 0x3963 → live_c2s fails
        pkt = {
            "cmd": 0x4013,
            "direction": "c2s",
            "seq": 1,
            "decrypted_body_hex": bytes(body).hex(),
        }
        assert parse_record(pkt) is None

    def test_s2c_wrong_magic_returns_none(self):
        """s2c 方向包 magic 不匹配 → 返回 None。"""
        body = bytearray(20)
        body[4:6] = b"\xFF\xFF"  # not 0x55AA → live_s2c fails
        body[0:4] = b"\x00\x13\x16\x00"  # opcode 0x1316 (valid)
        pkt = {
            "cmd": 0x4013,
            "direction": "s2c",
            "seq": 1,
            "decrypted_body_hex": bytes(body).hex(),
        }
        assert parse_record(pkt) is None

    def test_short_body_returns_none(self):
        """body 长度不足任何格式的最小头部长度 → 返回 None。"""
        for direction in ("s2c", "c2s"):
            pkt = {
                "cmd": 0x4013,
                "direction": direction,
                "seq": 1,
                "decrypted_body_hex": bytes(5).hex(),
            }
            assert parse_record(pkt) is None

    def test_wrong_cmd_returns_none(self):
        """cmd 不是 0x4013 → 返回 None。"""
        pkt = {
            "cmd": 0x1002,  # ACK 包，不是 DATA
            "direction": "s2c",
            "seq": 1,
            "decrypted_body_hex": bytes(20).hex(),
        }
        assert parse_record(pkt) is None

    def test_no_decrypted_body_returns_none(self):
        """没有 decrypted_body_hex → 返回 None。"""
        pkt = {
            "cmd": 0x4013,
            "direction": "s2c",
            "seq": 1,
        }
        assert parse_record(pkt) is None

    def test_empty_decrypted_body_returns_none(self):
        """decrypted_body_hex 为空字符串 → 返回 None。"""
        pkt = {
            "cmd": 0x4013,
            "direction": "s2c",
            "seq": 1,
            "decrypted_body_hex": "",
        }
        assert parse_record(pkt) is None