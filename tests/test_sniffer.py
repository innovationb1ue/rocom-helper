"""Sniffer 统计行为测试 — 验证 parse_fail 事件触发逻辑。"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, call
from src.capture.sniffer import Sniffer
from src.capture.frame import Be21Packet


def _make_be21(cmd: int, seq: int, direction: str, body: bytes = b"\x00" * 16) -> MagicMock:
    """构造一个假的 Be21Packet 用于测试。"""
    pkt = MagicMock(spec=Be21Packet)
    pkt.cmd = cmd
    pkt.seq = seq
    pkt.direction = direction
    pkt.body = body
    pkt.header_extra = b""
    pkt.body_len = len(body)
    return pkt


class TestSnifferParseFailStats:
    """验证 parse_fail 计数方向性：s2c 触发，c2s 不触发。"""

    def _make_sniffer(self):
        """创建带 mock on_event 的 Sniffer 实例。"""
        events = []
        def on_event(evt_type, data):
            events.append((evt_type, data))
        sniffer = Sniffer(preset_key=b"\x00" * 16)
        sniffer.on_event = on_event
        return sniffer, events

    def test_s2c_parse_fail_increments_stat_and_emits(self):
        """s2c 包 parse_record 返回 None → parse_fail += 1，_emit 触发。"""
        sniffer, events = self._make_sniffer()
        initial = sniffer.stats["parse_fail"]

        # s2c 方向，body 不匹配任何格式 → parse_record 返回 None
        fake_body = bytes(20)
        fake_body = bytes([0x00]*4) + b"\xFF\xFF" + bytes(12)  # wrong magic
        be21 = _make_be21(cmd=0x4013, seq=1, direction="s2c", body=fake_body)

        flow_mock = MagicMock()
        flow_mock.key = b"\x00" * 16
        flow_mock.flow_id = "test-flow"
        flow_mock.seen_acks = set()

        # 直接调用 _handle_be21 内部逻辑（通过 public 路径）
        # 这里用解密后的 body 直接测试 parse_record 失败路径
        from src.capture.crypto import decrypt_4013_body
        from src.protocol.proto_core import parse_record

        key = b"\x00" * 16
        # 用一个可解密但格式不对的 body
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        import os
        iv = os.urandom(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        wrong_body = bytes([0x00]*4) + b"\xFF\xFF" + bytes(12)  # 20 bytes, no tsf4g
        encrypted = iv + cipher.encrypt(pad(wrong_body, 16))

        be21.body = encrypted
        be21.header_extra = b""

        sniffer._handle_be21(flow_mock, be21)

        assert sniffer.stats["parse_fail"] == initial + 1
        assert any(e[0] == "parse_fail" for e in events)

    def test_c2s_benign_parse_fail_does_not_increment_stat(self):
        """c2s 包 parse_record 返回 None → parse_fail 不变，不 emit parse_fail。"""
        sniffer, events = self._make_sniffer()
        initial = sniffer.stats["parse_fail"]

        from src.capture.crypto import decrypt_4013_body
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        import os

        key = b"\x00" * 16
        iv = os.urandom(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        # 224B c2s body: 不匹配任何已知格式
        wrong_body = bytes(224)
        encrypted = iv + cipher.encrypt(pad(wrong_body, 16))

        be21 = _make_be21(cmd=0x4013, seq=1625, direction="c2s", body=encrypted)
        be21.header_extra = b""

        flow_mock = MagicMock()
        flow_mock.key = key
        flow_mock.flow_id = "test-flow"
        flow_mock.seen_acks = set()

        sniffer._handle_be21(flow_mock, be21)

        # c2s benign → stats 不增加，不 emit parse_fail
        assert sniffer.stats["parse_fail"] == initial
        assert not any(e[0] == "parse_fail" for e in events)
        # 但仍然写日志（通过 plog），且返回（不 crash）