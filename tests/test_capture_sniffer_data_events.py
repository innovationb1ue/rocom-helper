"""Sniffer DATA 帧处理测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import src.capture.sniffer_data_events as data_events
from src.capture.frame import Be21Packet
from src.capture.reassembly import FlowState
from src.capture.sniffer_data_events import handle_data_frame


def _make_flow(key: bytes | None = b"1234567890abcdef") -> FlowState:
    return FlowState(
        flow_id="127.0.0.1:10000-127.0.0.1:8195",
        client_ip="127.0.0.1",
        client_port=10000,
        server_ip="127.0.0.1",
        server_port=8195,
        key=key,
    )


def _make_be21(cmd: int = 0x4013, direction: str = "s2c") -> MagicMock:
    pkt = MagicMock(spec=Be21Packet)
    pkt.cmd = cmd
    pkt.seq = 11
    pkt.direction = direction
    pkt.header_extra = b"\xaa"
    pkt.body = b"\x01\x02"
    pkt.body_len = len(pkt.body)
    return pkt


def _stats() -> dict[str, int]:
    return {"decrypt_ok": 0, "decrypt_fail": 0, "key_miss": 0, "parse_fail": 0}


def test_non_data_frame_is_not_consumed():
    assert handle_data_frame(
        flow=_make_flow(),
        be21=_make_be21(cmd=0x1001),
        stats=_stats(),
        emit=MagicMock(),
    ) is False


def test_missing_key_uses_suppression_path_and_consumes_frame():
    flow = _make_flow(key=None)
    stats = _stats()
    emitted = []

    handled = handle_data_frame(
        flow=flow,
        be21=_make_be21(),
        stats=stats,
        emit=lambda event_type, data: emitted.append((event_type, data)),
    )

    assert handled is True
    assert stats["key_miss"] == 1
    assert flow.key_miss_count == 1
    assert emitted == []


def test_decrypt_failure_increments_stat_logs_and_emits(monkeypatch):
    def fail_decrypt(_key, _body):
        raise ValueError("bad padding")

    monkeypatch.setattr(data_events, "decrypt_4013_body", fail_decrypt)
    stats = _stats()
    emitted = []
    packet_logger = MagicMock()

    handled = handle_data_frame(
        flow=_make_flow(),
        be21=_make_be21(),
        stats=stats,
        emit=lambda event_type, data: emitted.append((event_type, data)),
        packet_logger=packet_logger,
    )

    assert handled is True
    assert stats["decrypt_fail"] == 1
    assert emitted[0][0] == "decrypt_fail"
    assert emitted[0][1]["reason"] == "bad padding"
    packet_logger.log_be21_frame.assert_called_once()


def test_parse_none_reports_s2c_parse_fail(monkeypatch):
    monkeypatch.setattr(data_events, "decrypt_4013_body", lambda _key, _body: (b"iv", b"plain"))
    monkeypatch.setattr(data_events, "parse_record", lambda _pkt: None)
    stats = _stats()
    emitted = []

    handled = handle_data_frame(
        flow=_make_flow(),
        be21=_make_be21(direction="s2c"),
        stats=stats,
        emit=lambda event_type, data: emitted.append((event_type, data)),
        packet_logger=MagicMock(),
    )

    assert handled is True
    assert stats["parse_fail"] == 1
    assert emitted[0][0] == "parse_fail"


def test_stale_preset_key_parse_fail_degrades_without_error_log(monkeypatch):
    monkeypatch.setattr(data_events, "decrypt_4013_body", lambda _key, _body: (b"iv", b"plain"))
    monkeypatch.setattr(data_events, "parse_record", lambda _pkt: None)
    flow = _make_flow()
    flow.key_from_preset = True
    stats = _stats()
    emitted = []
    packet_logger = MagicMock()
    be21 = _make_be21(direction="s2c")

    for seq in range(1, 4):
        be21.seq = seq
        handled = handle_data_frame(
            flow=flow,
            be21=be21,
            stats=stats,
            emit=lambda event_type, data: emitted.append((event_type, data)),
            packet_logger=packet_logger,
        )
        assert handled is True

    assert flow.key is None
    assert flow.key_from_preset is False
    assert flow.key_missing_suppressed is True
    assert flow.key_miss_count == 3
    assert stats["parse_fail"] == 0
    assert stats["key_miss"] == 1
    assert emitted == [
        (
            "key_missing_suppressed",
            {
                "flow_id": flow.flow_id,
                "cmd": 0x4013,
                "seq": 3,
                "key_miss_count": 3,
                "reason": "已保存密钥无法解析当前连接，可能已过期；后续该连接将降级静默，等待重新捕获密钥",
            },
        ),
    ]
    packet_logger.log_be21_frame.assert_not_called()


def test_inner_message_opcode_is_silently_consumed(monkeypatch):
    monkeypatch.setattr(data_events, "decrypt_4013_body", lambda _key, _body: (b"iv", b"plain"))
    monkeypatch.setattr(data_events, "parse_record", lambda _pkt: {"opcode": 0x0414})
    stats = _stats()
    emit = MagicMock()
    record_callback = MagicMock()
    packet_logger = MagicMock()

    handled = handle_data_frame(
        flow=_make_flow(),
        be21=_make_be21(),
        stats=stats,
        emit=emit,
        record_callback=record_callback,
        packet_logger=packet_logger,
    )

    assert handled is True
    assert stats["decrypt_ok"] == 0
    emit.assert_not_called()
    record_callback.assert_not_called()
    packet_logger.log_be21_frame.assert_not_called()


def test_successful_record_adds_summary_logs_dispatches_and_emits(monkeypatch):
    record = {"opcode": 0x1316}
    monkeypatch.setattr(data_events, "decrypt_4013_body", lambda _key, _body: (b"iv", b"plain"))
    monkeypatch.setattr(data_events, "parse_record", lambda _pkt: record)
    monkeypatch.setattr(data_events, "summarize", lambda rec, inner: ("battle_enter", "对战开始"))
    stats = _stats()
    emitted = []
    records = []
    packet_logger = MagicMock()
    flow = _make_flow()

    handled = handle_data_frame(
        flow=flow,
        be21=_make_be21(),
        stats=stats,
        emit=lambda event_type, data: emitted.append((event_type, data)),
        record_callback=records.append,
        packet_logger=packet_logger,
    )

    assert handled is True
    assert stats["decrypt_ok"] == 1
    assert record["_summary_kind"] == "battle_enter"
    assert record["_summary"] == "对战开始"
    assert flow.valid_record_count == 1
    assert records == [record]
    assert emitted == [("record", {"record": record})]
    packet_logger.log_be21_frame.assert_called_once()
