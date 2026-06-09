"""SnifferManager 的异步运行时任务。

只管理事件队列、WebSocket 广播循环和监控循环；不理解抓包状态语义。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from src.api.ws_hub import JsonWebSocketHub

logger = logging.getLogger(__name__)

MonitorTick = Callable[[int], Awaitable[int]]


class SnifferRuntime:
    """维护 SnifferManager 运行期所需的 asyncio 基础设施。"""

    def __init__(
        self,
        *,
        hub: JsonWebSocketHub,
        monitor_tick: MonitorTick,
        monitor_interval: float = 1.0,
    ) -> None:
        self._hub = hub
        self._monitor_tick = monitor_tick
        self._monitor_interval = monitor_interval
        self._event_queue: Optional[asyncio.Queue[Dict[str, Any]]] = None
        self._broadcast_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def ensure_started(self) -> None:
        """确保事件队列和后台任务绑定到当前 asyncio loop。"""
        self._loop = asyncio.get_running_loop()
        if self._event_queue is None:
            self._event_queue = asyncio.Queue()
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    def cancel_tasks(self) -> None:
        """取消后台任务；保留队列以保持既有重启行为。"""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            self._broadcast_task = None
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

    def push(self, msg: Dict[str, Any]) -> None:
        if self._event_queue is None or self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._event_queue.put_nowait, msg)
        except RuntimeError:
            logger.warning("_push: 无法提交事件到队列")

    def call_soon_threadsafe(self, callback: Callable[..., Any], *args: Any) -> None:
        if self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(callback, *args)
        except Exception:
            pass

    async def _broadcast_loop(self) -> None:
        """从队列取事件，广播给所有 WebSocket 客户端。"""
        if self._event_queue is None:
            return
        while True:
            try:
                msg = await self._event_queue.get()
            except asyncio.CancelledError:
                return
            await self._hub.broadcast(msg)

    async def _monitor_loop(self) -> None:
        """定期执行抓包状态监控 tick。"""
        last_flow_count = 0
        while True:
            try:
                await asyncio.sleep(self._monitor_interval)
                last_flow_count = await self._monitor_tick(last_flow_count)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.error("_monitor_loop 异常: %s", exc, exc_info=True)
