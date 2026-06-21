"""Sniffer monitor WebSocket helper 测试。"""
from __future__ import annotations

import asyncio
import json

from src.api.sniffer_ws_monitor import (
    handle_monitor_connection,
    handle_monitor_message,
    is_websocket_disconnect_error,
    send_monitor_status,
    status_event_from_manager,
)


class WebSocketDisconnect(Exception):
    pass


class FakeManager:
    def __init__(self) -> None:
        self.calls = 0
        self.added = []
        self.removed = []

    def get_status(self):
        self.calls += 1
        return {
            "status": "listening",
            "message": "监听中",
            "flow_count": 2,
            "key_hex": "abcd",
            "sniffer_running": True,
            "key_miss": 0,
            "decrypt_fail": 0,
            "parse_fail": 0,
        }

    def add_client(self, ws):
        self.added.append(ws)

    def remove_client(self, ws):
        self.removed.append(ws)


class FakeWebSocket:
    def __init__(self, raw_messages=None, *, fail_send: bool = False) -> None:
        self.texts = []
        self.raw_messages = list(raw_messages or [])
        self.accepted = False
        self.fail_send = fail_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, text: str) -> None:
        if self.fail_send:
            raise RuntimeError("send failed")
        self.texts.append(text)

    async def receive_text(self) -> str:
        if not self.raw_messages:
            raise WebSocketDisconnect()
        return self.raw_messages.pop(0)


def test_status_event_from_manager_uses_ws_contract_fields_only():
    manager = FakeManager()

    assert status_event_from_manager(manager) == {
        "type": "status",
        "status": "listening",
        "message": "监听中",
        "flow_count": 2,
        "key_hex": "abcd",
    }


def test_send_monitor_status_serializes_utf8_status():
    async def _run():
        ws = FakeWebSocket()

        await send_monitor_status(ws, FakeManager())

        assert json.loads(ws.texts[0])["message"] == "监听中"

    asyncio.run(_run())


def test_handle_monitor_connection_accepts_sends_initial_status_and_cleans_up():
    async def _run():
        ws = FakeWebSocket([json.dumps({"type": "get_status"}), "{bad"])
        manager = FakeManager()

        await handle_monitor_connection(ws, manager)

        assert ws.accepted is True
        assert manager.added == [ws]
        assert manager.removed == [ws]
        assert len(ws.texts) == 2
        assert [json.loads(text)["type"] for text in ws.texts] == ["status", "status"]

    asyncio.run(_run())


def test_handle_monitor_connection_removes_client_when_initial_status_send_fails():
    async def _run():
        ws = FakeWebSocket(fail_send=True)
        manager = FakeManager()

        await handle_monitor_connection(ws, manager)

        assert ws.accepted is True
        assert manager.added == [ws]
        assert manager.removed == [ws]

    asyncio.run(_run())


def test_is_websocket_disconnect_error_uses_duck_typed_exception_name():
    assert is_websocket_disconnect_error(WebSocketDisconnect()) is True
    assert is_websocket_disconnect_error(RuntimeError("boom")) is False


def test_handle_monitor_message_replies_to_get_status_and_ignores_bad_json():
    async def _run():
        ws = FakeWebSocket()
        manager = FakeManager()

        await handle_monitor_message(ws, manager, "{bad")
        await handle_monitor_message(ws, manager, json.dumps({"type": "ping"}))
        await handle_monitor_message(ws, manager, json.dumps({"type": "get_status"}))

        assert len(ws.texts) == 1
        assert json.loads(ws.texts[0])["type"] == "status"

    asyncio.run(_run())
