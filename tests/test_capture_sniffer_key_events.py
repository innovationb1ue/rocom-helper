"""Sniffer ACK key 帧处理测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

from src.capture.frame import Be21Packet
from src.capture.reassembly import FlowState
from src.capture.sniffer_key_events import handle_ack_key_frame


def _make_flow() -> FlowState:
    flow = FlowState(
        flow_id="127.0.0.1:10000-127.0.0.1:8195",
        client_ip="127.0.0.1",
        client_port=10000,
        server_ip="127.0.0.1",
        server_port=8195,
    )
    flow.key_miss_count = 3
    flow.key_missing_suppressed = True
    flow.key_missing_reported = True
    return flow


def _make_be21(cmd: int, seq: int, header_extra: bytes = b"", body: bytes = b"") -> MagicMock:
    pkt = MagicMock(spec=Be21Packet)
    pkt.cmd = cmd
    pkt.seq = seq
    pkt.direction = "s2c"
    pkt.header_extra = header_extra
    pkt.body = body
    pkt.body_len = len(body)
    return pkt


def test_non_ack_key_frame_is_not_consumed(tmp_path):
    events = []
    pkt_logger = MagicMock()

    handled = handle_ack_key_frame(
        flow=_make_flow(),
        be21=_make_be21(cmd=0x4013, seq=1),
        key_file=str(tmp_path / "session_key.txt"),
        emit=lambda event_type, data: events.append((event_type, data)),
        packet_logger=pkt_logger,
    )

    assert handled is False
    assert events == []
    pkt_logger.log_be21_frame.assert_not_called()


def test_ack_key_frame_sets_flow_key_resets_missing_state_and_emits(tmp_path):
    events = []
    flow = _make_flow()
    flow.key_from_preset = True
    key = b"1234567890abcdef"
    pkt_logger = MagicMock()

    handled = handle_ack_key_frame(
        flow=flow,
        be21=_make_be21(cmd=0x1002, seq=10, header_extra=b"\x00\x00" + key),
        key_file=str(tmp_path / "session_key.txt"),
        emit=lambda event_type, data: events.append((event_type, data)),
        packet_logger=pkt_logger,
    )

    assert handled is True
    assert flow.key == key
    assert flow.key_from_preset is False
    assert flow.key_miss_count == 0
    assert flow.key_missing_suppressed is False
    assert flow.key_missing_reported is False
    assert events == [
        ("key_captured", {"flow_id": flow.flow_id, "key_hex": key.hex()}),
    ]
    assert (tmp_path / "session_key.txt").exists()
    pkt_logger.log_key_extracted.assert_called_once_with(flow.flow_id, key)
    pkt_logger.log_be21_frame.assert_called_once()


def test_duplicate_ack_key_frame_logs_frame_but_does_not_emit_or_save_again(tmp_path):
    events = []
    flow = _make_flow()
    key = b"1234567890abcdef"
    be21 = _make_be21(cmd=0x1002, seq=10, header_extra=b"\x00\x00" + key)
    pkt_logger = MagicMock()
    key_file = tmp_path / "session_key.txt"

    for _ in range(2):
        assert handle_ack_key_frame(
            flow=flow,
            be21=be21,
            key_file=str(key_file),
            emit=lambda event_type, data: events.append((event_type, data)),
            packet_logger=pkt_logger,
        ) is True

    assert events == [
        ("key_captured", {"flow_id": flow.flow_id, "key_hex": key.hex()}),
    ]
    assert pkt_logger.log_key_extracted.call_count == 1
    assert pkt_logger.log_be21_frame.call_count == 2
