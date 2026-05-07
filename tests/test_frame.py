"""BE21 帧解析测试。"""
from __future__ import annotations

import pytest
from src.capture.frame import (
    MAGIC,
    FIXED_HDR_LEN,
    Be21Packet,
    parse_be21_from_buffer,
)


# --- 测试数据 ---

# BE21 帧头布局 (21 bytes fixed):
# [0:2]   MAGIC      0x33 0x66
# [2:6]   unknown    4 bytes (reserved / version / etc.)
# [6:8]   cmd        2 bytes BE
# [8:9]   unknown    1 byte
# [9:13]  seq        4 bytes BE
# [13:17] hdr_len    4 bytes BE (>= 21)
# [17:21] body_len   4 bytes BE
def _build_be21_frame(cmd: int, seq: int = 1, body: bytes = b"\x00" * 4,
                      direction: str = "s2c") -> bytearray:
    """构建一个有效的 BE21 帧用于测试。"""
    hdr_len = FIXED_HDR_LEN
    body_len = len(body)
    buf = bytearray()
    buf += MAGIC                                        # [0:2]
    buf += b"\x00" * 4                                  # [2:6] reserved
    buf += cmd.to_bytes(2, "big")                       # [6:8] cmd
    buf += b"\x00"                                      # [8:9] unknown
    buf += seq.to_bytes(4, "big")                       # [9:13] seq
    buf += hdr_len.to_bytes(4, "big")                   # [13:17] hdr_len
    buf += body_len.to_bytes(4, "big")                  # [17:21] body_len
    buf += body
    assert len(buf) == hdr_len + body_len
    return buf


class TestBe21Magic:
    """MAGIC 校验测试。"""

    def test_valid_magic(self):
        buf = _build_be21_frame(cmd=0x1316, body=b"\xAA\xBB")
        packets, consumed = parse_be21_from_buffer(buf, "s2c", 0)
        assert len(packets) == 1
        assert packets[0].cmd == 0x1316

    def test_invalid_magic_returns_empty(self):
        buf = bytearray(b"\x00\x00" + b"\x00" * 30)
        packets, consumed = parse_be21_from_buffer(buf, "s2c", 0)
        assert len(packets) == 0

    def test_no_magic_in_data(self):
        buf = bytearray(b"\xAA\xBB\xCC" * 10)
        packets, consumed = parse_be21_from_buffer(buf, "s2c", 0)
        assert len(packets) == 0


class TestBe21FrameParsing:
    """帧解析核心测试。"""

    def test_single_frame(self):
        body = b"\xDE\xAD\xBE\xEF"
        buf = _build_be21_frame(cmd=0x4013, seq=42, body=body)
        packets, consumed = parse_be21_from_buffer(buf, "s2c", 0)
        assert len(packets) == 1
        p = packets[0]
        assert p.cmd == 0x4013
        assert p.seq == 42
        assert p.body == body
        assert p.direction == "s2c"
        assert p.hdr_len == FIXED_HDR_LEN
        assert p.body_len == len(body)
        assert consumed == len(buf)

    def test_two_frames_back_to_back(self):
        buf1 = _build_be21_frame(cmd=0x1001, seq=1, body=b"\x11")
        buf2 = _build_be21_frame(cmd=0x1002, seq=2, body=b"\x22\x33")
        combined = buf1 + buf2
        packets, consumed = parse_be21_from_buffer(combined, "c2s", 0)
        assert len(packets) == 2
        assert packets[0].cmd == 0x1001
        assert packets[1].cmd == 0x1002
        assert packets[0].body == b"\x11"
        assert packets[1].body == b"\x22\x33"

    def test_direction_preserved(self):
        buf = _build_be21_frame(cmd=0x1316, direction="c2s")
        packets, _ = parse_be21_from_buffer(buf, "c2s", 0)
        assert packets[0].direction == "c2s"

    def test_empty_body(self):
        buf = _build_be21_frame(cmd=0x013D, body=b"")
        packets, _ = parse_be21_from_buffer(buf, "s2c", 0)
        assert len(packets) == 1
        assert packets[0].body == b""
        assert packets[0].body_len == 0


class TestBe21CmdRange:
    """cmd 范围校验测试。"""

    def test_valid_cmd_low(self):
        buf = _build_be21_frame(cmd=0x0001)
        packets, _ = parse_be21_from_buffer(buf, "s2c", 0)
        assert len(packets) == 1
        assert packets[0].cmd == 0x0001

    def test_valid_cmd_high(self):
        buf = _build_be21_frame(cmd=0x7FFF)
        packets, _ = parse_be21_from_buffer(buf, "s2c", 0)
        assert len(packets) == 1
        assert packets[0].cmd == 0x7FFF

    def test_cmd_zero_rejected(self):
        buf = _build_be21_frame(cmd=0x0000)
        packets, _ = parse_be21_from_buffer(buf, "s2c", 0)
        assert len(packets) == 0

    def test_cmd_too_high_rejected(self):
        buf = _build_be21_frame(cmd=0x8000)
        packets, _ = parse_be21_from_buffer(buf, "s2c", 0)
        assert len(packets) == 0


class TestBe21Truncation:
    """帧截断/不完整测试。"""

    def test_header_only_no_body(self):
        buf = _build_be21_frame(cmd=0x1316, body=b"\x00\x00")
        truncated = buf[:FIXED_HDR_LEN]  # only header, no body
        packets, consumed = parse_be21_from_buffer(truncated, "s2c", 0)
        assert len(packets) == 0

    def test_partial_header(self):
        buf = _build_be21_frame(cmd=0x1316)
        partial = buf[:10]  # less than FIXED_HDR_LEN
        packets, consumed = parse_be21_from_buffer(partial, "s2c", 0)
        assert len(packets) == 0

    def test_partial_body(self):
        buf = _build_be21_frame(cmd=0x1316, body=b"\x00" * 8)
        partial = buf[:FIXED_HDR_LEN + 4]  # body only half received
        packets, consumed = parse_be21_from_buffer(partial, "s2c", 0)
        assert len(packets) == 0


class TestBe21StreamOffset:
    """stream_offset 测试。"""

    def test_start_offset_zero(self):
        buf = _build_be21_frame(cmd=0x1316)
        packets, _ = parse_be21_from_buffer(buf, "s2c", 0)
        assert packets[0].stream_offset == 0

    def test_start_offset_nonzero(self):
        frame = _build_be21_frame(cmd=0x1316)
        # Add 100 bytes of padding before the frame
        buf = bytearray(b"\x00" * 100) + frame
        packets, _ = parse_be21_from_buffer(buf, "s2c", 0)
        assert len(packets) == 1
        assert packets[0].stream_offset == 100
