"""Battle route action helper tests."""
from __future__ import annotations

import asyncio
from pathlib import Path

import src.api.battle_route_actions as route_actions


class FakeManager:
    def __init__(self, state):
        self.state = state
        self.get_state_calls = 0

    def get_state(self):
        self.get_state_calls += 1
        return self.state


def test_battle_state_payload_returns_manager_state():
    manager = FakeManager({"phase": "resolving"})

    assert route_actions.battle_state_payload(manager) == {"phase": "resolving"}
    assert manager.get_state_calls == 1


def test_battle_pets_route_payload_projects_state_once():
    manager = FakeManager(
        {
            "my_pets": [{"name": "我方"}],
            "opp_pets": [{"name": "敌方"}],
            "my_active": {"name": "我方"},
            "opp_active": {"name": "敌方"},
        }
    )

    assert route_actions.battle_pets_route_payload(manager) == {
        "my_pets": [{"name": "我方"}],
        "opp_pets": [{"name": "敌方"}],
        "my_active": {"name": "我方"},
        "opp_active": {"name": "敌方"},
    }
    assert manager.get_state_calls == 1


def test_battle_effects_route_payload_projects_state_once():
    manager = FakeManager(
        {
            "weather": {"name": "雨天"},
            "phase": "resolving",
            "my_pets": [{"name": "我方", "buffs": [{"id": 1}]}],
            "opp_pets": [],
        }
    )

    assert route_actions.battle_effects_route_payload(manager) == {
        "weather": {"name": "雨天"},
        "phase": "resolving",
        "my_buffs": [{"pet_name": "我方", "buffs": [{"id": 1}]}],
        "opp_buffs": [],
    }
    assert manager.get_state_calls == 1


def test_replay_battle_route_payload_forwards_route_params(monkeypatch):
    async def fake_replay_battle_packets_payload(**kwargs):
        return {"ok": kwargs}

    monkeypatch.setattr(
        route_actions,
        "replay_battle_packets_payload",
        fake_replay_battle_packets_payload,
    )

    async def _run():
        manager = object()
        result = await route_actions.replay_battle_route_payload(
            manager,
            project_root=Path("root"),
            session="battle_session_1",
            delay_ms=12,
            stop_round=7,
        )

        assert result == {
            "ok": {
                "manager": manager,
                "project_root": Path("root"),
                "session": "battle_session_1",
                "delay_ms": 12,
                "stop_round": 7,
            }
        }

    asyncio.run(_run())
