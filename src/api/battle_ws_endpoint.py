"""`/ws/battle` route-level WebSocket helpers."""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def is_websocket_disconnect_error(exc: BaseException) -> bool:
    return exc.__class__.__name__ == "WebSocketDisconnect"


async def handle_battle_ws_connection(ws: Any, manager: Any) -> None:
    """维护 battle WebSocket 连接生命周期。"""
    await manager.add_client(ws)
    try:
        while True:
            raw = await ws.receive_text()
            await handle_battle_ws_raw_message(ws, manager, raw)
    except Exception as exc:
        if not is_websocket_disconnect_error(exc):
            raise
        manager.remove_client(ws)
        logger.info("Battle WebSocket disconnected")


async def handle_battle_ws_raw_message(ws: Any, manager: Any, raw: str) -> None:
    """解码 battle WebSocket 原始文本消息并交给 manager 处理。"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        await ws.send_json({"type": "error", "message": "Invalid JSON"})
        return
    await manager.handle_message(ws, data)
