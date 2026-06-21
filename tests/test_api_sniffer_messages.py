"""Sniffer status/record 消息构建测试。"""
from __future__ import annotations

from types import SimpleNamespace

from src.api.sniffer_messages import build_status_event, build_status_payload, slim_record


def test_build_status_event_keeps_ws_contract():
    assert build_status_event(
        status="listening",
        message="监听中",
        flow_count=2,
        key_hex="abcd",
    ) == {
        "type": "status",
        "status": "listening",
        "message": "监听中",
        "flow_count": 2,
        "key_hex": "abcd",
    }


def test_build_status_payload_includes_sniffer_stats_when_running():
    sniffer = SimpleNamespace(
        is_running=True,
        stats={"key_miss": 1, "decrypt_fail": 2, "parse_fail": 3},
    )

    assert build_status_payload(
        status="key_captured",
        message="密钥已捕获",
        flow_count=4,
        key_hex="abcd",
        sniffer=sniffer,
    ) == {
        "status": "key_captured",
        "message": "密钥已捕获",
        "flow_count": 4,
        "key_hex": "abcd",
        "sniffer_running": True,
        "key_miss": 1,
        "decrypt_fail": 2,
        "parse_fail": 3,
    }


def test_build_status_payload_defaults_stats_when_not_running():
    payload = build_status_payload(
        status="idle",
        message="已停止",
        flow_count=0,
        key_hex=None,
        sniffer=None,
    )

    assert payload["sniffer_running"] is False
    assert payload["key_miss"] == 0
    assert payload["decrypt_fail"] == 0
    assert payload["parse_fail"] == 0


def test_slim_record_removes_binary_and_unknown_fields():
    assert slim_record({
        "opcode": 0x1316,
        "opcode_hex": "0x1316",
        "direction": "s2c",
        "payload": b"raw",
        "extra": "ignore",
        "captured_at": "12:00:00.000",
    }) == {
        "direction": "s2c",
        "opcode": 0x1316,
        "opcode_hex": "0x1316",
        "captured_at": "12:00:00.000",
    }


def test_slim_record_handles_missing_record():
    assert slim_record(None) == {}
