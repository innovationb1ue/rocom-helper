"""SnifferManager 状态转换测试。"""
from __future__ import annotations

from types import SimpleNamespace

from src.api.sniffer_manager import SnifferManager


def test_key_missing_suppression_sets_key_missing_without_stopping():
    mgr = SnifferManager()
    mgr._sniffer = SimpleNamespace(is_running=True, stats={"key_miss": 3})

    mgr._on_sniffer_event(
        "key_missing_suppressed",
        {
            "flow_id": "127.0.0.1:10000-127.0.0.1:8195",
            "key_miss_count": 3,
        },
    )

    status = mgr.get_status()
    assert status["status"] == "key_missing"
    assert status["sniffer_running"] is True
    assert status["key_miss"] == 3
    assert "密钥已错过" in status["message"]


def test_key_capture_overrides_key_missing_state():
    mgr = SnifferManager()
    mgr._sniffer = SimpleNamespace(is_running=True, stats={"key_miss": 3})
    mgr._save_key = lambda _key_hex, _flow_id: None

    mgr._on_sniffer_event(
        "key_missing_suppressed",
        {
            "flow_id": "127.0.0.1:10000-127.0.0.1:8195",
            "key_miss_count": 3,
        },
    )
    mgr._on_sniffer_event(
        "key_captured",
        {
            "flow_id": "127.0.0.1:10000-127.0.0.1:8195",
            "key_hex": "31323334353637383930616263646566",
        },
    )

    status = mgr.get_status()
    assert status["status"] == "key_captured"
    assert status["key_hex"] == "31323334353637383930616263646566"
    assert status["sniffer_running"] is True
