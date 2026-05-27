"""Integration test for the battle replay API endpoint."""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.analysis.constants import OPCODE_BATTLE_FINISH
from src.analysis.battle_report import BattleReportError, get_report_package, parse_opcode_hex, read_metadata


FIXTURE_SESSION = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def replay_response(client):
    resp = client.post("/api/battle/replay?delay_ms=0&session=battle_session_1")
    return resp.json()


class TestReplayEndpoint:
    def test_returns_ok(self, replay_response):
        assert replay_response["status"] == "ok", f"Unexpected status: {replay_response}"

    def test_packets_processed(self, replay_response):
        assert replay_response["processed"] > 0
        assert replay_response["processed"] == 176  # known packet count for session 1

    def test_battle_result(self, replay_response):
        assert replay_response["result"] is not None
        assert "WIN" in replay_response["result"]

    def test_rounds(self, replay_response):
        assert replay_response["rounds"] == 17

    def test_pet_counts(self, replay_response):
        assert replay_response["my_pets"] > 0
        assert replay_response["opp_pets"] > 0

    def test_formatted_events_produced(self, replay_response):
        assert replay_response["total_formatted_events"] > 0

    def test_invalid_session_returns_error(self, client):
        resp = client.post("/api/battle/replay?delay_ms=0&session=nonexistent_session")
        data = resp.json()
        assert data["status"] == "error"

    def test_replay_does_not_trigger_auto_archive(self, client, monkeypatch):
        from src.api.battle_manager import BattleManager

        original = BattleManager.process_event
        archive_flags = []

        async def _process_event(self, opcode, detail, *, enable_archive=True):
            archive_flags.append(enable_archive)
            return await original(self, opcode, detail, enable_archive=enable_archive)

        monkeypatch.setattr(BattleManager, "process_event", _process_event)

        resp = client.post("/api/battle/replay?delay_ms=0&session=battle_session_1")

        assert resp.json()["status"] == "ok"
        assert archive_flags
        assert set(archive_flags) == {False}


class TestReplayTrackerState:
    """Verify the tracker state after replay matches known battle data."""

    def test_tracker_has_state(self):
        from src.api.battle_manager import get_battle_manager
        mgr = get_battle_manager()
        assert mgr.tracker is not None
        state = mgr.tracker.get_state()
        assert state["battle_id"] is not None
        assert state["result"] is not None

    def test_six_opponent_pets(self):
        from src.api.battle_manager import get_battle_manager
        mgr = get_battle_manager()
        state = mgr.tracker.get_state()
        assert len(state["opp_pets"]) == 6

    def test_pet_names_valid(self):
        from src.api.battle_manager import get_battle_manager
        mgr = get_battle_manager()
        state = mgr.tracker.get_state()
        for p in state["my_pets"] + state["opp_pets"]:
            assert p["name"], f"Pet with empty name: {p}"
            assert p["max_hp"] > 0, f"Pet {p['name']} has no max_hp"
            assert p["current_hp"] >= 0, f"Pet {p['name']} has negative hp"


class TestBattleReportEndpoints:
    def test_list_reports(self, client, monkeypatch):
        from src.api import routes_battle

        summary = SimpleNamespace(
            report_id="session:1",
            session_id="session",
            battle_index=1,
            enter_ts="10:00:00.000",
            finish_ts="10:01:00.000",
            duration_seconds=60,
            complete=True,
            file_count=12,
            battle_packet_count=8,
            rounds=3,
            result="WIN",
            session_path="logs/packets/session",
        )
        monkeypatch.setattr(routes_battle, "scan_report_summaries", lambda: [summary])

        resp = client.get("/api/battle/reports")

        assert resp.status_code == 200
        data = resp.json()
        assert data["reports"][0]["report_id"] == "session:1"
        assert data["reports"][0]["complete"] is True

    def test_get_report_detail(self, client, monkeypatch):
        from src.api import routes_battle

        summary = SimpleNamespace(report_id="session:1", session_id="session", battle_index=1)
        monkeypatch.setattr(routes_battle, "get_report_summary", lambda report_id: summary)

        resp = client.get("/api/battle/reports/session%3A1")

        assert resp.status_code == 200
        assert resp.json()["report_id"] == "session:1"

    def test_download_report(self, client, monkeypatch):
        from src.api import routes_battle

        monkeypatch.setattr(
            routes_battle,
            "get_report_package",
            lambda report_id: ("raco-report_session_battle-1.raco-report", b"zip-bytes"),
        )

        resp = client.get("/api/battle/reports/session%3A1/download")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert resp.headers["x-report-filename"].endswith(".raco-report")
        assert resp.content == b"zip-bytes"

    def test_download_unfinished_report(self, client, monkeypatch, tmp_path: Path):
        from src.api import routes_battle

        if not FIXTURE_SESSION.exists():
            pytest.skip("battle_session_1 fixture not found")

        packet_root = tmp_path / "logs" / "packets"
        session_dir = packet_root / "2026-05-07_21-17-31_monitor"
        shutil.copytree(FIXTURE_SESSION, session_dir)
        for fpath in session_dir.glob("*.bin"):
            meta = read_metadata(fpath) or {}
            if parse_opcode_hex(meta) == OPCODE_BATTLE_FINISH:
                fpath.unlink()

        monkeypatch.setattr(
            routes_battle,
            "get_report_package",
            lambda report_id: get_report_package(report_id, packet_root),
        )

        resp = client.get("/api/battle/reports/2026-05-07_21-17-31_monitor%3A1/download")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert resp.headers["x-report-filename"].endswith(".raco-report")
        assert resp.content.startswith(b"PK")

    def test_invalid_report_returns_404(self, client, monkeypatch):
        from src.api import routes_battle

        def _raise(_report_id):
            raise BattleReportError("Battle not found")

        monkeypatch.setattr(routes_battle, "get_report_summary", _raise)

        resp = client.get("/api/battle/reports/missing%3A1")

        assert resp.status_code == 404


class TestBattleManagerArchiveToggle:
    def test_process_event_archives_by_default(self, monkeypatch):
        from src.api.battle_manager import BattleManager

        calls = []

        async def _archive():
            calls.append("archive")

        async def _run():
            mgr = BattleManager()
            monkeypatch.setattr(mgr, "_archive_completed_battle", _archive)
            await mgr.process_event(OPCODE_BATTLE_FINISH, {"result": "WIN"})
            await asyncio.sleep(0)

        asyncio.run(_run())

        assert calls == ["archive"]

    def test_process_event_can_disable_archive(self, monkeypatch):
        from src.api.battle_manager import BattleManager

        calls = []

        async def _archive():
            calls.append("archive")

        async def _run():
            mgr = BattleManager()
            monkeypatch.setattr(mgr, "_archive_completed_battle", _archive)
            await mgr.process_event(OPCODE_BATTLE_FINISH, {"result": "WIN"}, enable_archive=False)
            await asyncio.sleep(0)

        asyncio.run(_run())

        assert calls == []
