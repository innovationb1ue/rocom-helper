"""Sniffer 启动 helper 测试。"""
from __future__ import annotations

import asyncio
import sys
import time
from types import SimpleNamespace

import pytest

from src.api import sniffer_startup
from src.api.sniffer_startup import (
    SnifferStartupResources,
    create_sniffer,
    monitor_session_id,
    prepare_startup_resources,
    start_sniffer_threaded,
    wait_for_start_settle,
)
from src.capture import crypto, packet_logger


def test_monitor_session_id_uses_expected_suffix():
    assert monitor_session_id(strftime=lambda _fmt: "2026-06-07_12-00-00") == (
        "2026-06-07_12-00-00_monitor"
    )


def test_prepare_startup_resources_loads_key_and_packet_logger(monkeypatch, tmp_path):
    calls = []

    class FakePacketLogger:
        def __init__(self, *, session_id: str) -> None:
            self.session_id = session_id
            calls.append(("packet_logger", session_id))

    monkeypatch.setattr(crypto, "load_key_from_file", lambda path: calls.append(("load", path)) or b"1234")
    monkeypatch.setattr(packet_logger, "setup_sniffer_logging", lambda: calls.append(("setup", None)))
    monkeypatch.setattr(packet_logger, "PacketLogger", FakePacketLogger)
    monkeypatch.setattr(sniffer_startup, "monitor_session_id", lambda: "fixed_monitor")

    resources = prepare_startup_resources(tmp_path / "session_key.txt")

    assert resources.saved_key == b"1234"
    assert resources.key_hex == "31323334"
    assert resources.packet_logger.session_id == "fixed_monitor"
    assert calls == [
        ("setup", None),
        ("load", str(tmp_path / "session_key.txt")),
        ("packet_logger", "fixed_monitor"),
    ]


def test_create_sniffer_wires_saved_key_event_callback_and_packet_logger(monkeypatch):
    created = {}

    class FakeSniffer:
        def __init__(self, **kwargs) -> None:
            created.update(kwargs)

    monkeypatch.setitem(sys.modules, "src.capture.sniffer", SimpleNamespace(Sniffer=FakeSniffer))
    packet_log = object()

    def on_event(_event_type: str, _data: dict) -> None:
        return None

    sniffer = create_sniffer(
        SnifferStartupResources(saved_key=b"1234", packet_logger=packet_log),
        on_event=on_event,
    )

    assert isinstance(sniffer, FakeSniffer)
    assert created == {
        "preset_key": b"1234",
        "on_event": on_event,
        "packet_logger": packet_log,
    }


def test_start_sniffer_threaded_runs_blocking_start():
    class FakeSniffer:
        def __init__(self) -> None:
            self.started = False

        def start(self) -> None:
            self.started = True

    async def _run():
        sniffer = FakeSniffer()

        await start_sniffer_threaded(sniffer, timeout=1.0)

        assert sniffer.started is True

    asyncio.run(_run())


def test_start_sniffer_threaded_raises_timeout():
    class SlowSniffer:
        def start(self) -> None:
            time.sleep(0.05)

    async def _run():
        with pytest.raises(asyncio.TimeoutError):
            await start_sniffer_threaded(SlowSniffer(), timeout=0.001)

    asyncio.run(_run())


def test_wait_for_start_settle_accepts_zero_delay():
    asyncio.run(wait_for_start_settle(0))
