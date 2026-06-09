"""SnifferManager 异步运行时测试。"""
from __future__ import annotations

import asyncio
import json

from src.api.sniffer_runtime import SnifferRuntime
from src.api.ws_hub import JsonWebSocketHub


class FakeWebSocket:
    def __init__(self) -> None:
        self.texts = []

    async def send_text(self, text: str) -> None:
        self.texts.append(text)


def test_runtime_push_broadcasts_queued_events():
    async def _run():
        hub = JsonWebSocketHub()
        ws = FakeWebSocket()
        hub.add(ws)

        async def monitor_tick(last_flow_count: int) -> int:
            return last_flow_count

        runtime = SnifferRuntime(hub=hub, monitor_tick=monitor_tick, monitor_interval=10.0)
        runtime.ensure_started()
        runtime.push({"type": "status", "message": "监听中"})
        await asyncio.sleep(0.01)
        runtime.cancel_tasks()
        await asyncio.sleep(0)

        assert json.loads(ws.texts[0]) == {"type": "status", "message": "监听中"}

    asyncio.run(_run())


def test_runtime_call_soon_threadsafe_dispatches_callback():
    async def _run():
        called = []

        async def monitor_tick(last_flow_count: int) -> int:
            return last_flow_count

        runtime = SnifferRuntime(
            hub=JsonWebSocketHub(),
            monitor_tick=monitor_tick,
            monitor_interval=10.0,
        )
        runtime.ensure_started()
        runtime.call_soon_threadsafe(called.append, {"opcode_hex": "0x1316"})
        await asyncio.sleep(0.01)
        runtime.cancel_tasks()
        await asyncio.sleep(0)

        assert called == [{"opcode_hex": "0x1316"}]

    asyncio.run(_run())


def test_runtime_monitor_loop_carries_last_flow_count_between_ticks():
    async def _run():
        seen = []
        done = asyncio.Event()

        async def monitor_tick(last_flow_count: int) -> int:
            seen.append(last_flow_count)
            next_count = last_flow_count + 2
            if len(seen) == 3:
                done.set()
            return next_count

        runtime = SnifferRuntime(
            hub=JsonWebSocketHub(),
            monitor_tick=monitor_tick,
            monitor_interval=0.001,
        )
        runtime.ensure_started()
        await asyncio.wait_for(done.wait(), timeout=1.0)
        runtime.cancel_tasks()
        await asyncio.sleep(0)

        assert seen == [0, 2, 4]

    asyncio.run(_run())
