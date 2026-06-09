"""Battle WebSocket route helper tests."""
from __future__ import annotations

import asyncio
import json

from src.api.battle_ws_endpoint import (
    handle_battle_ws_connection,
    handle_battle_ws_raw_message,
    is_websocket_disconnect_error,
)


class WebSocketDisconnect(Exception):
    pass


class FakeWebSocket:
    def __init__(self, raw_messages=None) -> None:
        self.jsons = []
        self.raw_messages = list(raw_messages or [])

    async def send_json(self, message):
        self.jsons.append(message)

    async def receive_text(self):
        if not self.raw_messages:
            raise WebSocketDisconnect()
        return self.raw_messages.pop(0)


class FakeManager:
    def __init__(self) -> None:
        self.messages = []
        self.added = []
        self.removed = []

    async def add_client(self, ws):
        self.added.append(ws)

    def remove_client(self, ws):
        self.removed.append(ws)

    async def handle_message(self, ws, data):
        self.messages.append((ws, data))


def test_handle_battle_ws_raw_message_forwards_valid_json():
    async def _run():
        ws = FakeWebSocket()
        manager = FakeManager()

        await handle_battle_ws_raw_message(ws, manager, json.dumps({"type": "get_state"}))

        assert manager.messages == [(ws, {"type": "get_state"})]
        assert ws.jsons == []

    asyncio.run(_run())


def test_handle_battle_ws_connection_adds_dispatches_and_removes_client():
    async def _run():
        ws = FakeWebSocket([json.dumps({"type": "get_state"}), "{bad"])
        manager = FakeManager()

        await handle_battle_ws_connection(ws, manager)

        assert manager.added == [ws]
        assert manager.messages == [(ws, {"type": "get_state"})]
        assert ws.jsons == [{"type": "error", "message": "Invalid JSON"}]
        assert manager.removed == [ws]

    asyncio.run(_run())


def test_is_websocket_disconnect_error_uses_duck_typed_exception_name():
    assert is_websocket_disconnect_error(WebSocketDisconnect()) is True
    assert is_websocket_disconnect_error(RuntimeError("boom")) is False


def test_handle_battle_ws_raw_message_returns_legacy_invalid_json_error():
    async def _run():
        ws = FakeWebSocket()
        manager = FakeManager()

        await handle_battle_ws_raw_message(ws, manager, "{bad")

        assert manager.messages == []
        assert ws.jsons == [{"type": "error", "message": "Invalid JSON"}]

    asyncio.run(_run())
