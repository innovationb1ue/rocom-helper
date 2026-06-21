"""Battle replay endpoint helper tests."""
from __future__ import annotations

import asyncio
from pathlib import Path

from src.api import battle_replay_endpoint


def test_fixture_session_dir_uses_project_fixture_layout():
    assert battle_replay_endpoint.fixture_session_dir(Path("root"), "battle_session_1") == (
        Path("root") / "tests" / "fixtures" / "packets" / "battle_session_1"
    )


def test_replay_battle_packets_payload_returns_legacy_error_for_missing_session(tmp_path: Path):
    async def _run():
        return await battle_replay_endpoint.replay_battle_packets_payload(
            manager=object(),
            project_root=tmp_path,
            session="missing",
            delay_ms=0,
            stop_round=None,
        )

    payload = asyncio.run(_run())

    assert payload["status"] == "error"
    assert "Session not found:" in payload["message"]


def test_replay_battle_packets_payload_delegates_to_replay_service(monkeypatch, tmp_path: Path):
    session_dir = tmp_path / "tests" / "fixtures" / "packets" / "battle_session_1"
    session_dir.mkdir(parents=True)
    calls = []

    async def fake_replay_fixture_to_manager(**kwargs):
        calls.append(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(battle_replay_endpoint, "replay_fixture_to_manager", fake_replay_fixture_to_manager)

    async def _run():
        return await battle_replay_endpoint.replay_battle_packets_payload(
            manager="manager",
            project_root=tmp_path,
            session="battle_session_1",
            delay_ms=1,
            stop_round=7,
        )

    payload = asyncio.run(_run())

    assert payload == {"status": "ok"}
    assert calls == [{
        "manager": "manager",
        "session_dir": session_dir,
        "delay_ms": 1,
        "stop_round": 7,
    }]
