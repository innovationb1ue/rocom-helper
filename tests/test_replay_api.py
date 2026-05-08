"""Integration test for the battle replay API endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


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
