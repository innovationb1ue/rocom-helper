"""battle WebSocket 客户端命令处理测试。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.analysis.models import ProcessResult
from src.api.battle_ws_commands import handle_battle_ws_command


class FakeWebSocket:
    def __init__(self) -> None:
        self.jsons = []

    async def send_json(self, message) -> None:
        self.jsons.append(message)


class FakeProcessor:
    def __init__(self) -> None:
        self.state = {"round": 2, "opp_active": {"pet_name": "火神"}}
        self.reset_called = False
        self.events = []

    def process_event(self, opcode, detail):
        self.events.append((opcode, detail))
        return ProcessResult(
            state={"battle_id": 1, "round": 1},
            suggestions=[{"type": "info", "message": "建议"}],
        )

    def get_state(self):
        return self.state

    def reset(self):
        self.reset_called = True


def test_ws_command_event_keeps_legacy_state_and_suggestions_responses():
    async def _run():
        ws = FakeWebSocket()
        processor = FakeProcessor()

        await handle_battle_ws_command(
            ws,
            processor,  # type: ignore[arg-type]
            {"type": "event", "opcode": 0x1316, "detail": {"battle_id": 1}},
        )

        assert processor.events == [(0x1316, {"battle_id": 1})]
        assert ws.jsons == [
            {"type": "state_update", "state": {"battle_id": 1, "round": 1}},
            {"type": "suggestions", "suggestions": [{"type": "info", "message": "建议"}]},
        ]

    asyncio.run(_run())


def test_ws_command_get_state_reset_and_counter_pick():
    async def _run():
        ws = FakeWebSocket()
        processor = FakeProcessor()

        await handle_battle_ws_command(ws, processor, {"type": "get_state"})  # type: ignore[arg-type]
        await handle_battle_ws_command(ws, processor, {"type": "request_counter_pick"})  # type: ignore[arg-type]
        await handle_battle_ws_command(ws, processor, {"type": "reset"})  # type: ignore[arg-type]

        assert ws.jsons[0] == {"type": "state", "state": processor.state}
        assert ws.jsons[1]["type"] == "counter_pick"
        assert ws.jsons[1]["opponent"] == {"pet_name": "火神"}
        assert ws.jsons[2] == {"type": "reset", "message": "Tracker reset"}
        assert processor.reset_called is True

    asyncio.run(_run())


def test_ws_command_unknown_type_returns_error():
    async def _run():
        ws = FakeWebSocket()
        await handle_battle_ws_command(ws, SimpleNamespace(), {"type": "missing"})  # type: ignore[arg-type]

        assert ws.jsons == [{"type": "error", "message": "Unknown type: missing"}]

    asyncio.run(_run())
