"""Sniffer 非 DATA 控制帧处理测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import src.capture.sniffer_control_events as control_events
from src.capture.frame import Be21Packet
from src.capture.sniffer_control_events import handle_control_frame


def _make_flow() -> MagicMock:
    flow = MagicMock()
    flow.flow_id = "127.0.0.1:10000-127.0.0.1:8195"
    return flow


def _make_be21(cmd: int, body: bytes = b"\x01\x02") -> MagicMock:
    pkt = MagicMock(spec=Be21Packet)
    pkt.cmd = cmd
    pkt.seq = 7
    pkt.direction = "s2c"
    pkt.header_extra = b"\xaa\xbb"
    pkt.body = body
    pkt.body_len = len(body)
    return pkt


def test_data_frame_is_not_consumed(monkeypatch):
    parser = MagicMock()
    monkeypatch.setattr(control_events, "parse_tgcp_control_packet", parser)

    handled = handle_control_frame(
        flow=_make_flow(),
        be21=_make_be21(cmd=0x4013),
        emit=MagicMock(),
        record_callback=MagicMock(),
        packet_logger=MagicMock(),
    )

    assert handled is False
    parser.assert_not_called()


def test_control_frame_logs_dispatches_record_and_emits(monkeypatch):
    record = {"record_type": "control", "cmd": 0x1001}
    monkeypatch.setattr(control_events, "parse_tgcp_control_packet", lambda pkt: record)
    emitted = []
    records = []
    packet_logger = MagicMock()

    handled = handle_control_frame(
        flow=_make_flow(),
        be21=_make_be21(cmd=0x1001, body=b"\x03\x04"),
        emit=lambda event_type, data: emitted.append((event_type, data)),
        record_callback=records.append,
        packet_logger=packet_logger,
    )

    assert handled is True
    assert records == [record]
    assert emitted == [("record", {"record": record})]
    packet_logger.log_be21_frame.assert_called_once()
    _, _, cmd, seq, header_extra, body = packet_logger.log_be21_frame.call_args.args
    assert cmd == 0x1001
    assert seq == 7
    assert header_extra == b"\xaa\xbb"
    assert body == b"\x03\x04"


def test_control_frame_without_record_callback_preserves_no_emit_behavior(monkeypatch):
    record = {"record_type": "control", "cmd": 0x1001}
    monkeypatch.setattr(control_events, "parse_tgcp_control_packet", lambda pkt: record)
    emit = MagicMock()

    handled = handle_control_frame(
        flow=_make_flow(),
        be21=_make_be21(cmd=0x1001),
        emit=emit,
        record_callback=None,
        packet_logger=MagicMock(),
    )

    assert handled is True
    emit.assert_not_called()


def test_control_frame_with_no_record_still_logs_but_does_not_emit(monkeypatch):
    monkeypatch.setattr(control_events, "parse_tgcp_control_packet", lambda pkt: None)
    emit = MagicMock()
    record_callback = MagicMock()
    packet_logger = MagicMock()

    handled = handle_control_frame(
        flow=_make_flow(),
        be21=_make_be21(cmd=0x1001),
        emit=emit,
        record_callback=record_callback,
        packet_logger=packet_logger,
    )

    assert handled is True
    packet_logger.log_be21_frame.assert_called_once()
    emit.assert_not_called()
    record_callback.assert_not_called()
