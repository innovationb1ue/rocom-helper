"""Sniffer record callback dispatcher tests."""
from __future__ import annotations

from src.api.sniffer_record_callbacks import SnifferRecordCallbacks


class FakeRuntime:
    def __init__(self) -> None:
        self.calls = []

    def call_soon_threadsafe(self, callback, *args):
        self.calls.append((callback, args))


def test_record_callbacks_registers_in_order():
    callbacks = SnifferRecordCallbacks()
    first = object()
    second = object()

    callbacks.register(first)
    callbacks.register(second)

    assert callbacks.callbacks == [first, second]


def test_record_callbacks_dispatches_each_callback_through_runtime():
    callbacks = SnifferRecordCallbacks()
    runtime = FakeRuntime()
    record = {"opcode": 0x1316}

    def first(_record):
        return None

    def second(_record):
        return None

    callbacks.register(first)
    callbacks.register(second)
    callbacks.dispatch(record, runtime=runtime)

    assert runtime.calls == [
        (first, (record,)),
        (second, (record,)),
    ]


def test_record_callbacks_dispatches_none_record_for_compatibility():
    callbacks = SnifferRecordCallbacks()
    runtime = FakeRuntime()

    def callback(_record):
        return None

    callbacks.register(callback)
    callbacks.dispatch(None, runtime=runtime)

    assert runtime.calls == [(callback, (None,))]


def test_record_callbacks_noop_without_registered_callbacks():
    callbacks = SnifferRecordCallbacks()
    runtime = FakeRuntime()

    callbacks.dispatch({"record_type": "data"}, runtime=runtime)

    assert runtime.calls == []
