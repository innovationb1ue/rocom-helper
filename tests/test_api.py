"""FastAPI API 路由测试 — 使用 TestClient + 真实数据。"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestPets:
    def test_list_pets(self, client):
        resp = client.get("/api/pets")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["total"] > 0
        assert len(data["pets"]) > 0

    def test_list_pets_pagination(self, client):
        resp = client.get("/api/pets?limit=5&offset=0")
        data = resp.json()
        assert len(data["pets"]) <= 5

    def test_get_pet_detail(self, client):
        resp = client.get("/api/pets/14000001")
        assert resp.status_code == 200
        data = resp.json()
        assert "pet" in data

    def test_get_pet_not_found(self, client):
        resp = client.get("/api/pets/999999999")
        data = resp.json()
        assert data.get("error") == "Pet not found"


class TestSkills:
    def test_list_skills(self, client):
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    def test_list_skills_pagination(self, client):
        resp = client.get("/api/skills?limit=3")
        data = resp.json()
        assert len(data["skills"]) <= 3


class TestTypes:
    def test_list_types(self, client):
        resp = client.get("/api/types")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["types"]) == 21

    def test_type_matchups(self, client):
        resp = client.get("/api/types/1/matchups")
        assert resp.status_code == 200
        data = resp.json()
        assert "weaknesses" in data
        assert "resistances" in data

    def test_type_not_found(self, client):
        resp = client.get("/api/types/999/matchups")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("error") == "Type not found"


class TestTeams:
    def test_analyze_team(self, client):
        resp = client.post("/api/teams/analyze", json={"pet_ids": [14000001, 14000002]})
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data

    def test_coverage(self, client):
        resp = client.post("/api/teams/coverage", json={"pet_ids": [14000001]})
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data

    def test_counter(self, client):
        resp = client.post("/api/teams/counter", json={"opponent_ids": [14000001]})
        assert resp.status_code == 200
        data = resp.json()
        assert "counters" in data


class TestDataRoutes:
    def test_data_status(self, client):
        resp = client.get("/api/data/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["total_records"] > 0

    def test_data_refresh(self, client):
        resp = client.post("/api/data/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "refreshed"


class TestWebSocket:
    def test_battle_websocket(self, client):
        with client.websocket_connect("/ws/battle") as ws:
            # Initial connection message
            data = ws.receive_json()
            assert data["type"] == "connected"

            # Send battle enter event
            ws.send_json({
                "type": "event",
                "opcode": 0x1316,
                "detail": {
                    "battle_id": 1,
                    "battle_mode": 1,
                    "round": 0,
                    "max_round": 30,
                    "wrappers": [
                        {"pet_id": 100, "pet_name": "TestPet", "types": [1], "side": 1,
                         "hp": 300, "max_hp": 300},
                        {"pet_id": 200, "pet_name": "OppPet", "types": [2], "side": 401,
                         "hp": 350, "max_hp": 350},
                    ],
                },
            })
            state = ws.receive_json()
            assert state["type"] == "state_update"
            assert state["state"]["battle_id"] == 1

            # Get state — may receive suggestions first from the event
            ws.send_json({"type": "get_state"})
            # Drain any pending messages until we get "state"
            for _ in range(5):
                msg = ws.receive_json()
                if msg["type"] == "state":
                    break

            # Reset
            ws.send_json({"type": "reset"})
            reset_resp = ws.receive_json()
            assert reset_resp["type"] == "reset"
