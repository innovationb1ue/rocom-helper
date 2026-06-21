"""SnifferManager flow helper tests."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.api import sniffer_manager_flow
from src.api.sniffer_manager_flow import (
    cleanup_failed_start_flow,
    evaluate_current_sniffer_state,
    start_sniffer_manager_flow,
)
from src.api.sniffer_startup import SnifferStartupResources


class FakeRuntime:
    def __init__(self) -> None:
        self.ensure_started_calls = 0
        self.cancelled = 0

    def ensure_started(self) -> None:
        self.ensure_started_calls += 1

    def cancel_tasks(self) -> None:
        self.cancelled += 1


class FakeSniffer:
    def __init__(self, *, running=True, status=None) -> None:
        self.is_running = running
        self._status = status or {"flow_count": 0, "flows": []}
        self.stop_calls = 0
        self.started = False

    def get_status(self):
        return dict(self._status)

    def start(self):
        self.started = True

    def stop(self):
        self.stop_calls += 1


class FakeLogger:
    def __init__(self) -> None:
        self.infos = []

    def info(self, *args) -> None:
        self.infos.append(args)


def test_evaluate_current_sniffer_state_updates_flow_and_state():
    states = []
    flow_counts = []
    sniffer = FakeSniffer(
        status={
            "flow_count": 2,
            "flows": [{"has_key": True}],
        }
    )

    asyncio.run(evaluate_current_sniffer_state(
        sniffer=sniffer,
        current_state="listening",
        key_hex=None,
        set_flow_count=flow_counts.append,
        set_state=lambda state, message: states.append((state, message)),
    ))

    assert flow_counts == [2]
    assert states == [("key_captured", "密钥已获取，正在监听数据")]


def test_evaluate_current_sniffer_state_ignores_missing_or_stopped_sniffer():
    calls = []

    asyncio.run(evaluate_current_sniffer_state(
        sniffer=None,
        current_state="listening",
        key_hex=None,
        set_flow_count=lambda value: calls.append(("flow", value)),
        set_state=lambda state, message: calls.append(("state", state, message)),
    ))
    asyncio.run(evaluate_current_sniffer_state(
        sniffer=FakeSniffer(running=False, status={"flow_count": 3}),
        current_state="listening",
        key_hex=None,
        set_flow_count=lambda value: calls.append(("flow", value)),
        set_state=lambda state, message: calls.append(("state", state, message)),
    ))

    assert calls == []


def test_start_sniffer_manager_flow_reuses_running_sniffer():
    runtime = FakeRuntime()
    sniffer = FakeSniffer(status={"flow_count": 1, "flows": []})
    states = []
    flow_counts = []

    asyncio.run(start_sniffer_manager_flow(
        get_sniffer=lambda: sniffer,
        set_sniffer=lambda _sniffer: pytest.fail("should not replace running sniffer"),
        runtime=runtime,
        key_file="session_key.txt",
        start_timeout=1.0,
        get_state=lambda: "listening",
        get_key_hex=lambda: None,
        set_key_hex=lambda _key: pytest.fail("should not reload key"),
        set_flow_count=flow_counts.append,
        set_state=lambda state, message: states.append((state, message)),
        on_event=lambda _event_type, _data: None,
        log=FakeLogger(),
    ))

    assert runtime.ensure_started_calls == 1
    assert flow_counts == [1]
    assert states == [("connected", "游戏已连接，等待密钥...")]


def test_start_sniffer_manager_flow_loads_key_starts_and_evaluates(monkeypatch):
    runtime = FakeRuntime()
    created_sniffer = FakeSniffer(
        status={
            "flow_count": 1,
            "flows": [{"has_key": False}],
        }
    )
    state = {"sniffer": None, "key_hex": None, "current_state": "idle"}
    states = []
    flow_counts = []
    logger = FakeLogger()

    async def _start(sniffer, *, timeout):
        assert sniffer is created_sniffer
        assert timeout == 2.0
        sniffer.started = True

    async def _settle():
        return None

    monkeypatch.setattr(
        sniffer_manager_flow,
        "prepare_startup_resources",
        lambda _key_file: SnifferStartupResources(saved_key=b"\x01\x02", packet_logger=object()),
    )
    monkeypatch.setattr(sniffer_manager_flow, "create_sniffer", lambda _resources, *, on_event: created_sniffer)
    monkeypatch.setattr(sniffer_manager_flow, "start_sniffer_threaded", _start)
    monkeypatch.setattr(sniffer_manager_flow, "wait_for_start_settle", _settle)

    def _set_state(next_state, message):
        state["current_state"] = next_state
        states.append((next_state, message))

    asyncio.run(start_sniffer_manager_flow(
        get_sniffer=lambda: state["sniffer"],
        set_sniffer=lambda sniffer: state.__setitem__("sniffer", sniffer),
        runtime=runtime,
        key_file="session_key.txt",
        start_timeout=2.0,
        get_state=lambda: state["current_state"],
        get_key_hex=lambda: state["key_hex"],
        set_key_hex=lambda key_hex: state.__setitem__("key_hex", key_hex),
        set_flow_count=flow_counts.append,
        set_state=_set_state,
        on_event=lambda _event_type, _data: None,
        log=logger,
    ))

    assert runtime.ensure_started_calls == 1
    assert state["sniffer"] is created_sniffer
    assert created_sniffer.started is True
    assert state["key_hex"] == "0102"
    assert flow_counts == [1]
    assert states == [
        ("listening", "监听中（已加载密钥）"),
        ("key_captured", "密钥已获取，正在监听数据"),
    ]
    assert logger.infos[-1] == ("持久化 Sniffer 已启动",)


def test_start_sniffer_manager_flow_cleans_up_timeout(monkeypatch):
    runtime = FakeRuntime()
    sniffer = FakeSniffer()
    state = {"sniffer": None}
    states = []
    flow_counts = []

    async def _start(_sniffer, *, timeout):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(
        sniffer_manager_flow,
        "prepare_startup_resources",
        lambda _key_file: SnifferStartupResources(saved_key=None, packet_logger=object()),
    )
    monkeypatch.setattr(sniffer_manager_flow, "create_sniffer", lambda _resources, *, on_event: sniffer)
    monkeypatch.setattr(sniffer_manager_flow, "start_sniffer_threaded", _start)

    with pytest.raises(RuntimeError, match="Sniffer start timed out"):
        asyncio.run(start_sniffer_manager_flow(
            get_sniffer=lambda: state["sniffer"],
            set_sniffer=lambda next_sniffer: state.__setitem__("sniffer", next_sniffer),
            runtime=runtime,
            key_file="session_key.txt",
            start_timeout=0.1,
            get_state=lambda: "idle",
            get_key_hex=lambda: None,
            set_key_hex=lambda _key_hex: None,
            set_flow_count=flow_counts.append,
            set_state=lambda next_state, message: states.append((next_state, message)),
            on_event=lambda _event_type, _data: None,
            log=FakeLogger(),
        ))

    assert runtime.cancelled == 1
    assert sniffer.stop_calls == 1
    assert state["sniffer"] is None
    assert flow_counts == [0]
    assert states == [
        ("listening", "监听中，等待游戏连接..."),
        ("idle", "抓包启动超时，请确认已安装 Npcap 并尝试以管理员身份运行。"),
    ]


def test_cleanup_failed_start_flow_resets_sniffer_reference():
    runtime = FakeRuntime()
    sniffer = FakeSniffer()
    state = SimpleNamespace(sniffer=sniffer)
    states = []
    flow_counts = []

    cleanup_failed_start_flow(
        runtime=runtime,
        sniffer=sniffer,
        message="失败",
        set_state=lambda next_state, message: states.append((next_state, message)),
        set_flow_count=flow_counts.append,
        set_sniffer=lambda next_sniffer: setattr(state, "sniffer", next_sniffer),
    )

    assert runtime.cancelled == 1
    assert sniffer.stop_calls == 1
    assert state.sniffer is None
    assert flow_counts == [0]
    assert states == [("idle", "失败")]
