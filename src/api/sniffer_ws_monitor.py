"""Sniffer monitor WebSocket command helpers."""
from __future__ import annotations

import json
from typing import Any

from src.api.sniffer_messages import build_status_event


def status_event_from_manager(manager: Any) -> dict[str, Any]:
    """从 manager 当前状态构建 monitor WebSocket status 事件。"""
    status = manager.get_status()
    return build_status_event(
        status=status["status"],
        message=status["message"],
        flow_count=status["flow_count"],
        key_hex=status["key_hex"],
    )


async def send_monitor_status(ws: Any, manager: Any) -> None:
    """向 monitor WebSocket 发送当前 status 事件。"""
    await ws.send_text(json.dumps(status_event_from_manager(manager), ensure_ascii=False))


def is_websocket_disconnect_error(exc: BaseException) -> bool:
    return exc.__class__.__name__ == "WebSocketDisconnect"


async def handle_monitor_connection(ws: Any, manager: Any) -> None:
    """维护 sniffer monitor WebSocket 连接生命周期。"""
    await ws.accept()
    manager.add_client(ws)

    try:
        await send_monitor_status(ws, manager)
    except Exception:
        manager.remove_client(ws)
        return

    try:
        while True:
            raw = await ws.receive_text()
            await handle_monitor_message(ws, manager, raw)
    except Exception as exc:
        if not is_websocket_disconnect_error(exc):
            raise
    finally:
        manager.remove_client(ws)


async def handle_monitor_message(ws: Any, manager: Any, raw: str) -> None:
    """处理 monitor WebSocket 控制消息。"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return

    if data.get("type") == "get_status":
        await send_monitor_status(ws, manager)
