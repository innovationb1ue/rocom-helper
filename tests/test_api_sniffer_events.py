"""Sniffer 事件状态转换测试。"""
from __future__ import annotations

from datetime import datetime

from src.api.sniffer_events import SnifferEventHandler


def make_handler():
    state = {
        "status": "idle",
        "key_hex": None,
        "flow_count": 0,
        "events": [],
        "saved_keys": [],
        "records": [],
    }

    handler = SnifferEventHandler(
        get_state=lambda: state["status"],
        get_key_hex=lambda: state["key_hex"],
        set_key_hex=lambda key_hex: state.__setitem__("key_hex", key_hex),
        get_flow_count=lambda: state["flow_count"],
        set_flow_count=lambda count: state.__setitem__("flow_count", count),
        set_state=lambda status, message: state.update({"status": status, "message": message}),
        push=lambda event: state["events"].append(event),
        save_key=lambda key_hex, flow_id: state["saved_keys"].append((key_hex, flow_id)),
        dispatch_record_callbacks=lambda record: state["records"].append(record),
        now_factory=lambda: datetime(2026, 6, 7, 4, 45, 30, 123000),
    )
    return handler, state


def test_key_missing_event_sets_state_and_pushes_event():
    handler, state = make_handler()
    state["key_hex"] = "stale"

    handler.handle("key_missing_suppressed", {"flow_id": "flow-1", "key_miss_count": 3})

    assert state["status"] == "key_missing"
    assert state["key_hex"] is None
    assert state["saved_keys"] == [(None, "flow-1")]
    assert "密钥已错过" in state["message"]
    assert state["events"] == [
        {"type": "key_missing_suppressed", "flow_id": "flow-1", "key_miss_count": 3},
    ]


def test_key_captured_updates_key_saves_and_pushes_event():
    handler, state = make_handler()

    handler.handle("key_captured", {"flow_id": "flow-1", "key_hex": "abcd"})

    assert state["status"] == "key_captured"
    assert state["key_hex"] == "abcd"
    assert state["saved_keys"] == [("abcd", "flow-1")]
    assert state["events"] == [
        {"type": "key_captured", "flow_id": "flow-1", "key_hex": "abcd"},
    ]


def test_record_event_adds_capture_time_pushes_slim_record_and_dispatches_full_record():
    handler, state = make_handler()
    record = {
        "opcode": 0x1316,
        "opcode_hex": "0x1316",
        "payload": b"raw",
    }

    handler.handle("record", {"record": record})

    assert record["captured_at"] == "04:45:30.123"
    assert state["events"] == [
        {
            "type": "record",
            "record": {
                "opcode": 0x1316,
                "opcode_hex": "0x1316",
                "captured_at": "04:45:30.123",
            },
        },
    ]
    assert state["records"] == [record]


def test_first_traffic_moves_listening_state_based_on_key_presence():
    handler, state = make_handler()
    state["status"] = "listening"

    handler.on_first_traffic()

    assert state["flow_count"] == 1
    assert state["status"] == "connected"
    assert "等待密钥" in state["message"]

    state["status"] = "listening"
    state["key_hex"] = "abcd"
    handler.on_first_traffic()

    assert state["flow_count"] == 2
    assert state["status"] == "key_captured"
    assert "密钥已加载" in state["message"]


def test_flow_closed_never_drops_below_zero_and_marks_disconnected():
    handler, state = make_handler()

    handler.handle("flow_closed", {"flow_id": "flow-1"})

    assert state["flow_count"] == 0
    assert state["status"] == "disconnected"
    assert state["events"] == [{"type": "flow_closed", "flow_id": "flow-1"}]
