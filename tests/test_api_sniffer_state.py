"""Sniffer status 快照评估测试。"""
from __future__ import annotations

from src.api.sniffer_state import evaluate_sniffer_status


def test_evaluate_sniffer_status_keeps_idle_when_no_flows():
    result = evaluate_sniffer_status(
        {"flow_count": 0, "flows": []},
        current_state="listening",
        key_hex=None,
    )

    assert result.flow_count == 0
    assert result.next_state is None
    assert result.next_message is None


def test_evaluate_sniffer_status_detects_existing_flow_key():
    result = evaluate_sniffer_status(
        {"flow_count": 2, "flows": [{"has_key": False}, {"has_key": True}]},
        current_state="connected",
        key_hex=None,
    )

    assert result.flow_count == 2
    assert result.next_state == "key_captured"
    assert "密钥已获取" in result.next_message


def test_evaluate_sniffer_status_uses_loaded_key_even_when_flows_have_no_key():
    result = evaluate_sniffer_status(
        {"flow_count": 1, "flows": [{"has_key": False}]},
        current_state="listening",
        key_hex="abcd",
    )

    assert result.flow_count == 1
    assert result.next_state == "key_captured"


def test_evaluate_sniffer_status_marks_connected_only_from_listening():
    result = evaluate_sniffer_status(
        {"flow_count": 1, "flows": [{"has_key": False}]},
        current_state="listening",
        key_hex=None,
    )

    assert result.flow_count == 1
    assert result.next_state == "connected"
    assert "等待密钥" in result.next_message

    unchanged = evaluate_sniffer_status(
        {"flow_count": 1, "flows": [{"has_key": False}]},
        current_state="key_missing",
        key_hex=None,
    )

    assert unchanged.flow_count == 1
    assert unchanged.next_state is None


def test_evaluate_sniffer_status_clamps_bad_flow_count():
    result = evaluate_sniffer_status(
        {"flow_count": -3, "flows": [{"has_key": True}]},
        current_state="listening",
        key_hex=None,
    )

    assert result.flow_count == 0
    assert result.next_state is None
