"""Sniffer WebSocket/status 消息构建工具。"""
from __future__ import annotations

from typing import Any, Dict, Optional


def build_status_event(
    *,
    status: str,
    message: str,
    flow_count: int,
    key_hex: Optional[str],
) -> Dict[str, Any]:
    """构建 WebSocket status 事件。"""
    return {
        "type": "status",
        "status": status,
        "message": message,
        "flow_count": flow_count,
        "key_hex": key_hex,
    }


def build_status_payload(
    *,
    status: str,
    message: str,
    flow_count: int,
    key_hex: Optional[str],
    sniffer: Optional[Any],
) -> Dict[str, Any]:
    """构建 REST status payload。"""
    stats = {}
    sniffer_running = sniffer is not None and sniffer.is_running
    if sniffer_running:
        stats = sniffer.stats
    return {
        "status": status,
        "message": message,
        "flow_count": flow_count,
        "key_hex": key_hex,
        "sniffer_running": sniffer_running,
        "key_miss": stats.get("key_miss", 0),
        "decrypt_fail": stats.get("decrypt_fail", 0),
        "parse_fail": stats.get("parse_fail", 0),
    }


def slim_record(record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """精简 record 用于 WebSocket 推送（去掉二进制字段）。"""
    if not record:
        return {}
    out = {}
    for key in (
        "record_type",
        "transport_kind",
        "direction",
        "opcode",
        "opcode_hex",
        "cmd",
        "cmd_hex",
        "tgcp_command_name",
        "_summary_kind",
        "_summary",
        "transport_layout",
        "session_id_hex",
        "sub_id_hex",
        "captured_at",
    ):
        value = record.get(key)
        if value is not None:
            out[key] = value
    return out
