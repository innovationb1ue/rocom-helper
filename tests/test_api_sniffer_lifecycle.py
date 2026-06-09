"""Sniffer lifecycle helper tests."""
from __future__ import annotations

from types import SimpleNamespace

from src.api.sniffer_lifecycle import (
    cleanup_failed_sniffer_start,
    monitor_sniffer_flow_tick,
    packet_session_dir_from_sniffer,
    stop_sniffer_instance,
    stop_sniffer_runtime,
)


class FakeRuntime:
    def __init__(self) -> None:
        self.cancelled = 0

    def cancel_tasks(self) -> None:
        self.cancelled += 1


class FakeLogger:
    def __init__(self) -> None:
        self.warnings = []

    def warning(self, *args) -> None:
        self.warnings.append(args)


class FakeSniffer:
    def __init__(self, *, running: bool = True, fail_stop: bool = False, flow_count: int = 0) -> None:
        self.is_running = running
        self.fail_stop = fail_stop
        self.flow_count = flow_count
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1
        if self.fail_stop:
            raise RuntimeError("boom")


def test_stop_sniffer_instance_stops_running_sniffer():
    sniffer = FakeSniffer(running=True)

    stop_sniffer_instance(sniffer)

    assert sniffer.stop_calls == 1


def test_stop_sniffer_instance_ignores_missing_or_not_running_sniffer():
    stop_sniffer_instance(None)
    sniffer = FakeSniffer(running=False)

    stop_sniffer_instance(sniffer)

    assert sniffer.stop_calls == 0


def test_stop_sniffer_instance_logs_stop_errors():
    sniffer = FakeSniffer(running=True, fail_stop=True)
    log = FakeLogger()

    stop_sniffer_instance(sniffer, log=log)

    assert sniffer.stop_calls == 1
    assert len(log.warnings) == 1
    assert log.warnings[0][0] == "清理失败的 Sniffer 启动时出错: %s"
    assert str(log.warnings[0][1]) == "boom"


def test_cleanup_failed_sniffer_start_cancels_stops_and_sets_idle_state():
    runtime = FakeRuntime()
    sniffer = FakeSniffer(running=True)
    states = []
    flow_counts = []

    cleanup_failed_sniffer_start(
        runtime=runtime,
        sniffer=sniffer,
        message="失败",
        set_state=lambda state, message: states.append((state, message)),
        set_flow_count=flow_counts.append,
    )

    assert runtime.cancelled == 1
    assert sniffer.stop_calls == 1
    assert flow_counts == [0]
    assert states == [("idle", "失败")]


def test_stop_sniffer_runtime_resets_runtime_sniffer_flow_key_and_state():
    runtime = FakeRuntime()
    sniffer = FakeSniffer(running=True)
    states = []
    flow_counts = []
    keys = []

    stop_sniffer_runtime(
        runtime=runtime,
        sniffer=sniffer,
        set_state=lambda state, message: states.append((state, message)),
        set_flow_count=flow_counts.append,
        set_key_hex=keys.append,
    )

    assert runtime.cancelled == 1
    assert sniffer.stop_calls == 1
    assert flow_counts == [0]
    assert keys == [None]
    assert states == [("idle", "已停止")]


def test_packet_session_dir_from_sniffer_handles_missing_logger_and_session():
    assert packet_session_dir_from_sniffer(None) is None
    assert packet_session_dir_from_sniffer(SimpleNamespace()) is None
    assert packet_session_dir_from_sniffer(SimpleNamespace(pkt_logger=SimpleNamespace())) is None
    assert (
        packet_session_dir_from_sniffer(
            SimpleNamespace(pkt_logger=SimpleNamespace(session_dir="packets/session"))
        )
        == "packets/session"
    )


def test_monitor_sniffer_flow_tick_keeps_baseline_without_running_sniffer():
    calls = []

    assert monitor_sniffer_flow_tick(
        None,
        last_flow_count=3,
        on_first_traffic=lambda: calls.append("traffic"),
    ) == 3
    assert monitor_sniffer_flow_tick(
        FakeSniffer(running=False, flow_count=5),
        last_flow_count=3,
        on_first_traffic=lambda: calls.append("traffic"),
    ) == 3
    assert calls == []


def test_monitor_sniffer_flow_tick_reports_each_new_flow_and_returns_current_count():
    calls = []

    result = monitor_sniffer_flow_tick(
        FakeSniffer(running=True, flow_count=5),
        last_flow_count=2,
        on_first_traffic=lambda: calls.append("traffic"),
    )

    assert result == 5
    assert calls == ["traffic", "traffic", "traffic"]


def test_monitor_sniffer_flow_tick_does_not_emit_when_flow_count_does_not_increase():
    calls = []

    result = monitor_sniffer_flow_tick(
        FakeSniffer(running=True, flow_count=2),
        last_flow_count=5,
        on_first_traffic=lambda: calls.append("traffic"),
    )

    assert result == 2
    assert calls == []
