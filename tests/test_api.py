"""FastAPI API 路由测试 - PVP 工作台公开接口。"""
from __future__ import annotations

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


class TestWebSocket:
    def test_battle_websocket(self, client):
        with client.websocket_connect("/ws/battle") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"

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

            ws.send_json({"type": "get_state"})
            for _ in range(5):
                msg = ws.receive_json()
                if msg["type"] == "state":
                    break

            ws.send_json({"type": "reset"})
            reset_resp = ws.receive_json()
            assert reset_resp["type"] == "reset"
