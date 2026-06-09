"""WebSocket JSON 广播工具。

只负责连接列表、JSON 序列化和失效连接清理；不理解战斗事件语义。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List


class JsonWebSocketHub:
    """维护一组 WebSocket 客户端并广播 JSON 消息。"""

    def __init__(self) -> None:
        self._clients: List[Any] = []

    @property
    def clients(self) -> List[Any]:
        return self._clients

    def has_clients(self) -> bool:
        return bool(self._clients)

    def add(self, ws: Any) -> None:
        """注册一个已经由路由 accept 的 WebSocket。"""
        self._clients.append(ws)

    async def accept(self, ws: Any) -> None:
        await ws.accept()
        self.add(ws)

    def remove(self, ws: Any) -> None:
        if ws in self._clients:
            self._clients.remove(ws)

    async def send_json(self, ws: Any, message: Dict[str, Any]) -> None:
        await ws.send_json(message)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        text = json.dumps(message, ensure_ascii=False)
        dead: List[Any] = []
        for ws in self._clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove(ws)
