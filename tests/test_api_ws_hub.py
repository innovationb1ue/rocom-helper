"""WebSocket 广播工具测试。"""
from __future__ import annotations

import asyncio
import json

from src.api.ws_hub import JsonWebSocketHub


class FakeWebSocket:
    def __init__(self, *, fail_text: bool = False) -> None:
        self.accepted = False
        self.fail_text = fail_text
        self.texts = []
        self.jsons = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, text: str) -> None:
        if self.fail_text:
            raise RuntimeError("closed")
        self.texts.append(text)

    async def send_json(self, message) -> None:
        self.jsons.append(message)


def test_ws_hub_accepts_and_sends_connected_json():
    async def _run():
        hub = JsonWebSocketHub()
        ws = FakeWebSocket()

        await hub.accept(ws)
        await hub.send_json(ws, {"type": "connected", "message": "就绪"})

        assert ws.accepted is True
        assert hub.has_clients() is True
        assert ws.jsons == [{"type": "connected", "message": "就绪"}]

    asyncio.run(_run())


def test_ws_hub_can_register_already_accepted_socket():
    hub = JsonWebSocketHub()
    ws = FakeWebSocket()

    hub.add(ws)

    assert ws.accepted is False
    assert hub.clients == [ws]


def test_ws_hub_broadcast_serializes_utf8_and_removes_dead_clients():
    async def _run():
        hub = JsonWebSocketHub()
        alive = FakeWebSocket()
        dead = FakeWebSocket(fail_text=True)
        await hub.accept(alive)
        await hub.accept(dead)

        await hub.broadcast({"type": "state_update", "message": "能量"})

        assert json.loads(alive.texts[0]) == {"type": "state_update", "message": "能量"}
        assert hub.clients == [alive]

    asyncio.run(_run())
