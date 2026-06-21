"""持久化抓包管理器 — 单例，管理 Sniffer 生命周期，WebSocket 广播状态。"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import WebSocket

from src.config import settings
from src.api.sniffer_events import SnifferEventHandler
from src.api.sniffer_key_store import save_persistent_key
from src.api.sniffer_lifecycle import (
    monitor_sniffer_flow_tick,
    packet_session_dir_from_sniffer,
    stop_sniffer_runtime,
)
from src.api.sniffer_manager_flow import (
    evaluate_current_sniffer_state,
    start_sniffer_manager_flow,
)
from src.api.sniffer_messages import build_status_payload
from src.api.sniffer_record_callbacks import SnifferRecordCallbacks
from src.api.sniffer_runtime import SnifferRuntime
from src.api.sniffer_manager_state import SnifferManagerState
from src.api.ws_hub import JsonWebSocketHub

logger = logging.getLogger(__name__)

_PERSISTENT_KEY_FILE = settings.session_key_file
_SNIFFER_START_TIMEOUT_SECONDS = 8.0


class SnifferManager:
    """单例管理器，驱动持久化 Sniffer 并向 WebSocket 客户端广播事件。"""

    def __init__(self) -> None:
        self._sniffer: Optional[Any] = None
        self._ws_hub = JsonWebSocketHub()
        self._runtime = SnifferRuntime(
            hub=self._ws_hub,
            monitor_tick=self._monitor_sniffer_once,
        )
        self._state = SnifferManagerState()
        self._record_callbacks = SnifferRecordCallbacks()
        self._event_handler = SnifferEventHandler(
            get_state=lambda: self._state.state,
            get_key_hex=lambda: self._state.key_hex,
            set_key_hex=self._set_key_hex,
            get_flow_count=lambda: self._state.flow_count,
            set_flow_count=self._set_flow_count,
            set_state=self._set_state,
            push=self._push,
            save_key=lambda key_hex, flow_id: self._save_key(key_hex, flow_id),
            dispatch_record_callbacks=self._dispatch_record_callbacks,
        )

    @property
    def state(self) -> str:
        return self._state.state

    @property
    def state_message(self) -> str:
        return self._state.message

    def _set_state(self, state: str, message: str) -> None:
        event = self._state.set_state(state, message)
        if event is None:
            return
        logger.info("状态变更: %s — %s", state, message)
        self._push(event)

    def _set_key_hex(self, key_hex: Optional[str]) -> None:
        self._state.set_key_hex(key_hex)

    def _set_flow_count(self, flow_count: int) -> None:
        self._state.set_flow_count(flow_count)

    def _push(self, msg: Dict[str, Any]) -> None:
        self._runtime.push(msg)

    def register_record_callback(self, callback: Any) -> None:
        """注册回调，每条抓包记录会通过 call_soon_threadsafe 调用 callback(record)。"""
        self._record_callbacks.register(callback)

    def _dispatch_record_callbacks(self, record: Optional[Dict[str, Any]]) -> None:
        self._record_callbacks.dispatch(record, runtime=self._runtime)

    # ---- WebSocket 管理 ----

    def add_client(self, ws: WebSocket) -> None:
        self._ws_hub.add(ws)

    def remove_client(self, ws: WebSocket) -> None:
        self._ws_hub.remove(ws)

    # ---- 事件回调（在 Scapy 线程中调用） ----

    def _on_sniffer_event(self, event_type: str, data: Dict[str, Any]) -> None:
        self._event_handler.handle(event_type, data)

    def _on_first_traffic(self) -> None:
        self._event_handler.on_first_traffic()

    # ---- 监控循环 ----

    async def _monitor_sniffer_once(self, last_flow_count: int) -> int:
        """检查一次 Sniffer flow 数变化，返回新的基准 flow_count。"""
        return monitor_sniffer_flow_tick(
            self._sniffer,
            last_flow_count=last_flow_count,
            on_first_traffic=self._on_first_traffic,
        )

    # ---- 状态评估 ----

    async def _evaluate_current_state(self) -> None:
        """嗅探器启动后，根据实际流量和密钥状态评估并设置正确的状态。"""
        await evaluate_current_sniffer_state(
            sniffer=self._sniffer,
            current_state=self._state.state,
            key_hex=self._state.key_hex,
            set_flow_count=self._set_flow_count,
            set_state=self._set_state,
        )

    # ---- 启动/停止 ----

    async def start(self) -> None:
        """启动持久化 Sniffer。"""
        await start_sniffer_manager_flow(
            get_sniffer=lambda: self._sniffer,
            set_sniffer=self._set_sniffer,
            runtime=self._runtime,
            key_file=_PERSISTENT_KEY_FILE,
            start_timeout=_SNIFFER_START_TIMEOUT_SECONDS,
            get_state=lambda: self._state.state,
            get_key_hex=lambda: self._state.key_hex,
            set_key_hex=self._set_key_hex,
            set_flow_count=self._set_flow_count,
            set_state=self._set_state,
            on_event=self._on_sniffer_event,
            log=logger,
        )

    def _set_sniffer(self, sniffer: Optional[Any]) -> None:
        self._sniffer = sniffer

    async def stop(self) -> None:
        """停止 Sniffer。"""
        stop_sniffer_runtime(
            runtime=self._runtime,
            sniffer=self._sniffer,
            set_state=self._set_state,
            set_flow_count=self._set_flow_count,
            set_key_hex=self._set_key_hex,
        )
        self._sniffer = None

    def get_status(self) -> Dict[str, Any]:
        return build_status_payload(
            status=self._state.state,
            message=self._state.message,
            flow_count=self._state.flow_count,
            key_hex=self._state.key_hex,
            sniffer=self._sniffer,
        )

    def get_packet_session_dir(self) -> Optional[Any]:
        return packet_session_dir_from_sniffer(self._sniffer)

    def _save_key(self, key_hex: Optional[str], flow_id: str) -> None:
        save_persistent_key(_PERSISTENT_KEY_FILE, key_hex, flow_id)


# 全局单例
_manager = SnifferManager()


def get_sniffer_manager() -> SnifferManager:
    return _manager
