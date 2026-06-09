"""Sniffer REST route action helper tests."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from src.api.sniffer_route_actions import (
    sniffer_status_payload,
    start_sniffer_payload,
    stop_sniffer_payload,
)


class FakeManager:
    def __init__(self, *, state: str = "idle", start_error: Exception | None = None) -> None:
        self.state = state
        self.state_message = "当前状态消息"
        self.start_error = start_error
        self.started = False
        self.stopped = False

    def get_status(self) -> dict:
        return {"status": self.state, "started": self.started, "stopped": self.stopped}

    async def start(self) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


def test_start_sniffer_payload_keeps_already_running_contract():
    manager = FakeManager(state="listening")

    payload = asyncio.run(start_sniffer_payload(manager))

    assert payload == {
        "status": "already_running",
        "message": "已在监听中",
        "details": {"status": "listening", "started": False, "stopped": False},
    }
    assert manager.started is False


def test_start_sniffer_payload_starts_and_returns_status():
    manager = FakeManager()

    payload = asyncio.run(start_sniffer_payload(manager))

    assert payload == {
        "status": "ok",
        "message": "监听已启动",
        "details": {"status": "idle", "started": True, "stopped": False},
    }


def test_start_sniffer_payload_translates_start_errors_to_http():
    manager = FakeManager(start_error=RuntimeError("timeout"))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(start_sniffer_payload(manager))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "当前状态消息"

    manager = FakeManager(start_error=ValueError("bad"))
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(start_sniffer_payload(manager))
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "bad"


def test_stop_and_status_payloads_keep_contract():
    manager = FakeManager()

    stopped = asyncio.run(stop_sniffer_payload(manager))
    status = sniffer_status_payload(manager)

    assert stopped == {
        "status": "ok",
        "message": "监听已停止",
        "details": {"status": "idle", "started": False, "stopped": True},
    }
    assert status == {
        "status": "ok",
        "details": {"status": "idle", "started": False, "stopped": True},
    }
