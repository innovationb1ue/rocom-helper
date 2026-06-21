"""SnifferManager 运行状态容器。"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from src.api.sniffer_messages import build_status_event


class SnifferManagerState:
    """保存 manager 状态字段，并生成状态变更 WebSocket 事件。"""

    def __init__(
        self,
        *,
        state: str = "idle",
        message: str = "未启动",
        key_hex: Optional[str] = None,
        flow_count: int = 0,
    ) -> None:
        self._state = state
        self._message = message
        self._key_hex = key_hex
        self._flow_count = flow_count
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        return self._state

    @property
    def message(self) -> str:
        return self._message

    @property
    def key_hex(self) -> Optional[str]:
        return self._key_hex

    @property
    def flow_count(self) -> int:
        return self._flow_count

    def set_key_hex(self, key_hex: Optional[str]) -> None:
        self._key_hex = key_hex

    def set_flow_count(self, flow_count: int) -> None:
        with self._lock:
            self._flow_count = flow_count

    def set_state(self, state: str, message: str) -> Optional[Dict[str, Any]]:
        """更新状态，若发生变更则返回需要广播的 status event。"""
        if self._state == state and self._message == message:
            return None
        self._state = state
        self._message = message
        return build_status_event(
            status=state,
            message=message,
            flow_count=self._flow_count,
            key_hex=self._key_hex,
        )
