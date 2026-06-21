"""Sniffer 原始事件到 manager 状态和 WebSocket 消息的转换。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, Optional

from src.api.sniffer_messages import slim_record


class SnifferEventHandler:
    """处理抓包线程事件，保持 SnifferManager 生命周期编排更薄。"""

    def __init__(
        self,
        *,
        get_state: Callable[[], str],
        get_key_hex: Callable[[], Optional[str]],
        set_key_hex: Callable[[Optional[str]], None],
        get_flow_count: Callable[[], int],
        set_flow_count: Callable[[int], None],
        set_state: Callable[[str, str], None],
        push: Callable[[Dict[str, Any]], None],
        save_key: Callable[[Optional[str], str], None],
        dispatch_record_callbacks: Callable[[Optional[Dict[str, Any]]], None],
        now_factory: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._get_state = get_state
        self._get_key_hex = get_key_hex
        self._set_key_hex = set_key_hex
        self._get_flow_count = get_flow_count
        self._set_flow_count = set_flow_count
        self._set_state = set_state
        self._push = push
        self._save_key = save_key
        self._dispatch_record_callbacks = dispatch_record_callbacks
        self._now_factory = now_factory

    def handle(self, event_type: str, data: Dict[str, Any]) -> None:
        """处理来自 capture.Sniffer 的单个事件。"""
        if event_type == "flow_closed":
            self._handle_flow_closed(data)
        elif event_type == "key_captured":
            self._handle_key_captured(data)
        elif event_type == "key_missing_suppressed":
            self._set_key_hex(None)
            self._save_key(None, data.get("flow_id", ""))
            self._set_state("key_missing", "密钥已错过，请重启游戏或重新连接后再监听")
            self._push({"type": "key_missing_suppressed", **data})
        elif event_type in {"decrypt_fail", "parse_fail"}:
            self._push({"type": event_type, **data})
        elif event_type == "record":
            self._handle_record(data)

    def on_first_traffic(self) -> None:
        """记录首包流量，并按当前密钥状态推进连接状态。"""
        flow_count = self._get_flow_count() + 1
        self._set_flow_count(flow_count)
        if self._get_state() != "listening":
            return
        if self._get_key_hex():
            self._set_state("key_captured", "密钥已加载，正在监听数据")
        else:
            self._set_state("connected", "游戏已连接，等待密钥...")

    def _handle_flow_closed(self, data: Dict[str, Any]) -> None:
        flow_count = max(0, self._get_flow_count() - 1)
        self._set_flow_count(flow_count)
        if flow_count == 0:
            self._set_state("disconnected", "游戏连接已断开")
        self._push({"type": "flow_closed", **data})

    def _handle_key_captured(self, data: Dict[str, Any]) -> None:
        key_hex = data.get("key_hex")
        self._set_key_hex(key_hex)
        self._save_key(key_hex, data.get("flow_id", ""))
        self._set_state("key_captured", "密钥已捕获，正在监听数据")
        self._push({"type": "key_captured", **data})

    def _handle_record(self, data: Dict[str, Any]) -> None:
        full_record = data.get("record")
        if full_record is not None:
            full_record["captured_at"] = self._now_factory().strftime("%H:%M:%S.%f")[:-3]
        self._push({"type": "record", "record": slim_record(full_record)})
        self._dispatch_record_callbacks(full_record)
