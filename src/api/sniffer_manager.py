"""持久化抓包管理器 — 单例，管理 Sniffer 生命周期，WebSocket 广播状态。"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from src.protocol.proto_core import TGCP_COMMAND_NAMES

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_PERSISTENT_KEY_FILE = _PROJECT_ROOT / "logs" / "session_key.txt"


class SnifferManager:
    """单例管理器，驱动持久化 Sniffer 并向 WebSocket 客户端广播事件。"""

    def __init__(self) -> None:
        self._sniffer: Optional[Any] = None
        self._ws_clients: List[WebSocket] = []
        self._event_queue: Optional[asyncio.Queue[Dict[str, Any]]] = None
        self._broadcast_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._state = "idle"  # idle | listening | connected | key_captured | disconnected
        self._state_message = "未启动"
        self._key_hex: Optional[str] = None
        self._flow_count = 0
        self._lock = threading.Lock()
        self._record_callbacks: List[Any] = []

    @property
    def state(self) -> str:
        return self._state

    @property
    def state_message(self) -> str:
        return self._state_message

    def _set_state(self, state: str, message: str) -> None:
        if self._state == state and self._state_message == message:
            return
        self._state = state
        self._state_message = message
        logger.info("状态变更: %s — %s", state, message)
        self._push({"type": "status", "status": state, "message": message,
                     "flow_count": self._flow_count, "key_hex": self._key_hex})

    def _push(self, msg: Dict[str, Any]) -> None:
        if self._event_queue is not None and self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(self._event_queue.put_nowait, msg)
            except RuntimeError:
                logger.warning("_push: 无法提交事件到队列")

    def register_record_callback(self, callback: Any) -> None:
        """注册回调，每条抓包记录会通过 call_soon_threadsafe 调用 callback(record)。"""
        self._record_callbacks.append(callback)

    def _dispatch_record_callbacks(self, record: Dict[str, Any]) -> None:
        if self._loop is None:
            return
        for cb in self._record_callbacks:
            try:
                self._loop.call_soon_threadsafe(cb, record)
            except Exception:
                logger.warning("record callback dispatch failed", exc_info=True)

    # ---- WebSocket 管理 ----

    def add_client(self, ws: WebSocket) -> None:
        self._ws_clients.append(ws)

    def remove_client(self, ws: WebSocket) -> None:
        if ws in self._ws_clients:
            self._ws_clients.remove(ws)

    async def _broadcast_loop(self) -> None:
        """从队列取事件，广播给所有 WebSocket 客户端。"""
        while True:
            try:
                msg = await self._event_queue.get()
            except asyncio.CancelledError:
                return
            text = json.dumps(msg, ensure_ascii=False)
            dead = []
            for ws in self._ws_clients:
                try:
                    await ws.send_text(text)
                except Exception:
                    logger.debug("sniffer broadcast send failed, removing client")
                    dead.append(ws)
            for ws in dead:
                self._ws_clients.remove(ws)

    # ---- 事件回调（在 Scapy 线程中调用） ----

    def _on_sniffer_event(self, event_type: str, data: Dict[str, Any]) -> None:
        if event_type == "flow_closed":
            with self._lock:
                self._flow_count = max(0, self._flow_count - 1)
            if self._flow_count == 0:
                self._set_state("disconnected", "游戏连接已断开")
            self._push({"type": "flow_closed", **data})
        elif event_type == "key_captured":
            self._key_hex = data.get("key_hex")
            self._save_key(data.get("key_hex"), data.get("flow_id", ""))
            self._set_state("key_captured", "密钥已捕获，正在监听数据")
            self._push({"type": "key_captured", **data})
        elif event_type == "key_stale":
            self._key_hex = None
            if self._flow_count > 0:
                self._set_state(
                    "connected",
                    "密钥可能过期，等待新密钥（如一直无密钥请重启游戏）",
                )
            self._push({"type": "key_stale", **data})
        elif event_type == "record":
            full_record = data.get("record")
            if full_record is not None:
                full_record["captured_at"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self._push({"type": "record", "record": _slim_record(full_record)})
            self._dispatch_record_callbacks(full_record)

    def _on_first_traffic(self) -> None:
        with self._lock:
            self._flow_count += 1
        if self._state == "listening":
            if self._key_hex:
                self._set_state("key_captured", "密钥已加载，正在监听数据")
            else:
                self._set_state("connected", "游戏已连接，等待密钥（如一直无密钥请重启游戏）")

    # ---- 监控循环 ----

    async def _monitor_loop(self) -> None:
        """定期检查 Sniffer 状态，检测首包、心跳超时等。"""
        last_flow_count = 0
        while True:
            try:
                await asyncio.sleep(1.0)
                if self._sniffer is None or not self._sniffer.is_running:
                    continue

                current_count = self._sniffer.flow_count
                if current_count > last_flow_count:
                    for _ in range(current_count - last_flow_count):
                        self._on_first_traffic()
                last_flow_count = current_count
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.error("_monitor_loop 异常: %s", exc, exc_info=True)

    # ---- 状态评估 ----

    async def _evaluate_current_state(self) -> None:
        """嗅探器启动后，根据实际流量和密钥状态评估并设置正确的状态。"""
        if self._sniffer is None or not self._sniffer.is_running:
            return

        status = self._sniffer.get_status()
        flow_count = status.get("flow_count", 0)
        flows = status.get("flows", [])

        with self._lock:
            self._flow_count = flow_count

        if flow_count == 0:
            return

        any_has_key = any(f.get("has_key", False) for f in flows)
        if any_has_key or self._key_hex:
            self._set_state("key_captured", "密钥已获取，正在监听数据")
        elif self._state == "listening":
            self._set_state("connected", "游戏已连接，等待密钥（如一直无密钥请重启游戏）")

    # ---- 启动/停止 ----

    async def start(self) -> None:
        """启动持久化 Sniffer。"""
        if self._sniffer is not None and self._sniffer.is_running:
            # Sniffer 仍在运行 — 重建事件基础设施并重新评估状态
            if self._event_queue is None:
                self._event_queue = asyncio.Queue()
            if self._broadcast_task is None or self._broadcast_task.done():
                self._broadcast_task = asyncio.create_task(self._broadcast_loop())
            if self._monitor_task is None or self._monitor_task.done():
                self._monitor_task = asyncio.create_task(self._monitor_loop())
            self._loop = asyncio.get_running_loop()
            await self._evaluate_current_state()
            return

        from src.capture.sniffer import Sniffer
        from src.capture.packet_logger import PacketLogger, setup_sniffer_logging
        from src.capture.crypto import load_key_from_file

        setup_sniffer_logging()

        saved_key = load_key_from_file(str(_PERSISTENT_KEY_FILE))
        if saved_key:
            self._key_hex = saved_key.hex()
            logger.info("加载已保存密钥: %s", self._key_hex)

        import time
        session_id = time.strftime("%Y-%m-%d_%H-%M-%S") + "_monitor"
        pkt_log = PacketLogger(session_id=session_id)

        # 1. 先创建事件基础设施，再启动嗅探器（避免竞态）
        self._event_queue = asyncio.Queue()
        self._loop = asyncio.get_running_loop()
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        # 2. 设置初始状态
        if saved_key:
            self._set_state("listening", "监听中（已加载密钥）")
        else:
            self._set_state("listening", "监听中，等待游戏连接...")

        # 3. 创建并启动嗅探器（此后开始抓包）
        self._sniffer = Sniffer(
            preset_key=saved_key,
            on_event=self._on_sniffer_event,
            packet_logger=pkt_log,
        )
        self._sniffer.start()

        # 4. 短暂等待后评估实际状态（游戏可能已打开）
        await asyncio.sleep(0.3)
        await self._evaluate_current_state()

        logger.info("持久化 Sniffer 已启动")

    async def stop(self) -> None:
        """停止 Sniffer。"""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            self._broadcast_task = None
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        if self._sniffer:
            try:
                self._sniffer.stop()
            except Exception as exc:
                logger.warning("停止 Sniffer 时出错: %s", exc)
            self._sniffer = None
        self._flow_count = 0
        self._key_hex = None
        self._set_state("idle", "已停止")

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": self._state,
            "message": self._state_message,
            "flow_count": self._flow_count,
            "key_hex": self._key_hex,
            "sniffer_running": self._sniffer is not None and self._sniffer.is_running,
        }

    def _save_key(self, key_hex: Optional[str], flow_id: str) -> None:
        if not key_hex:
            return
        try:
            key = bytes.fromhex(key_hex)
            _PERSISTENT_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            from src.capture.crypto import write_key_file
            write_key_file(str(_PERSISTENT_KEY_FILE), key, flow_id)
            logger.info("密钥已保存到 %s", _PERSISTENT_KEY_FILE)
        except Exception as exc:
            logger.warning("保存密钥失败: %s", exc)


def _slim_record(record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """精简 record 用于 WebSocket 推送（去掉二进制字段）。"""
    if not record:
        return {}
    out = {}
    for k in ("record_type", "transport_kind", "direction", "opcode", "opcode_hex",
              "cmd", "cmd_hex", "tgcp_command_name", "_summary_kind", "_summary",
              "transport_layout", "session_id_hex", "sub_id_hex", "captured_at"):
        v = record.get(k)
        if v is not None:
            out[k] = v
    return out


# 全局单例
_manager = SnifferManager()


def get_sniffer_manager() -> SnifferManager:
    return _manager
