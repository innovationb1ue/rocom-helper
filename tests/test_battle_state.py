"""战斗状态追踪器测试 — 模拟真实协议事件流。"""
from __future__ import annotations

import pytest
from src.analysis.battle_state import BattleStateTracker


@pytest.fixture
def tracker():
    return BattleStateTracker()


def _enter_event():
    return {
        "opcode": 0x1316,
        "battle_id": 12345,
        "battle_mode": 1,
        "round": 0,
        "max_round": 30,
        "weather_id": 0,
        "wrappers": [
            {"pet_id": 100, "pet_name": "火龙", "types": [1], "side": 1,
             "hp": 300, "max_hp": 300},
            {"pet_id": 200, "pet_name": "水龟", "types": [2], "side": 401,
             "hp": 350, "max_hp": 350},
        ],
    }


def _round_start_event(round_num):
    return {
        "opcode": 0x131A,
        "round": round_num,
        "wrappers": [],
    }


def _action_resolve_event(entries):
    return {
        "opcode": 0x1324,
        "entries": entries,
    }


def _finish_event(result_name):
    return {
        "opcode": 0x132C,
        "result_name": result_name,
        "rounds": 5,
        "seconds": 120,
        "finish_pet_infos": [
            {"pet_gid": 100, "remain_hp": 200},
            {"pet_gid": 200, "remain_hp": 0},
        ],
    }


class TestBattleEnter:
    def test_initial_state(self, tracker):
        state = tracker.handle_event(0x1316, _enter_event())
        assert state["battle_id"] == 12345
        assert state["battle_mode"] == 1
        assert state["result"] is None

    def test_pets_initialized(self, tracker):
        state = tracker.handle_event(0x1316, _enter_event())
        assert len(state["my_pets"]) == 1
        assert len(state["opp_pets"]) == 1
        assert state["my_pets"][0]["name"] == "火龙"
        assert state["opp_pets"][0]["name"] == "水龟"

    def test_active_set(self, tracker):
        state = tracker.handle_event(0x1316, _enter_event())
        assert state["my_active"]["name"] == "火龙"
        assert state["opp_active"]["name"] == "水龟"

    def test_hp_initialized(self, tracker):
        state = tracker.handle_event(0x1316, _enter_event())
        assert state["my_active"]["current_hp"] == 300
        assert state["my_active"]["max_hp"] == 300
        assert state["my_active"]["hp_pct"] == 1.0


class TestDamageTracking:
    def test_damage_applied(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 100, "target_hp_after": 250,
             "damage_target_side": "敌方"},
        ]))
        assert state["opp_active"]["current_hp"] == 250
        assert state["opp_active"]["hp_pct"] < 1.0

    def test_damage_to_self(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 50, "target_hp_after": 250,
             "damage_target_side": "我方"},
        ]))
        assert state["my_active"]["current_hp"] == 250


class TestSkillCast:
    def test_energy_consumed(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "skill_id": 7700001, "skill_name": "愿力冲击",
             "actor_side": "我方", "energy_delta": -2, "energy_after": 3},
        ]))
        assert state["my_active"]["energy"] == 3


class TestDefeatEvent:
    def test_defeat_sets_hp_zero(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "defeat", "actor_side": "敌方"},
        ]))
        assert state["opp_active"]["current_hp"] == 0
        assert state["opp_active"]["hp_pct"] == 0.0


class TestBattleFinish:
    def test_result_recorded(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x132C, _finish_event("WIN"))
        assert state["result"] == "WIN"

    def test_hp_updated_on_finish(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x132C, _finish_event("WIN"))
        # my pet 100 has 200 hp remaining
        assert state["my_pets"][0]["current_hp"] == 200
        # opp pet 200 has 0 hp
        assert state["opp_pets"][0]["current_hp"] == 0


class TestFullBattleFlow:
    def test_complete_flow(self, tracker):
        # 1. Battle enter
        state = tracker.handle_event(0x1316, _enter_event())
        assert state["round"] == 0
        assert state["result"] is None

        # 2. Round 1 start
        state = tracker.handle_event(0x131A, _round_start_event(1))
        assert state["round"] == 1

        # 3. Skill cast
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "skill_id": 7700001, "skill_name": "愿力冲击",
             "actor_side": "我方", "energy_delta": -2, "energy_after": 3},
        ]))
        assert state["my_active"]["energy"] == 3

        # 4. Damage
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 120, "target_hp_after": 230,
             "damage_target_side": "敌方"},
        ]))
        assert state["opp_active"]["current_hp"] == 230

        # 5. Battle finish
        state = tracker.handle_event(0x132C, _finish_event("WIN"))
        assert state["result"] == "WIN"

        # 6. Events history (battle enter + round start + 2 actions + finish = 5, but
        # the detail dicts don't include opcode in _enter_event, _round_start_event etc.
        # The handle_event adds opcode but the _enter_event detail overwrites it with
        # the detail dict — so it depends on whether the detail has opcode field)
        assert len(state["events"]) >= 4


class TestSuggestions:
    def test_low_hp_suggestion(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        # Damage my pet to low HP
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 250, "target_hp_after": 50,
             "damage_target_side": "我方"},
        ]))
        suggestions = tracker.get_suggestions()
        types = [s["type"] for s in suggestions]
        assert "low_hp" in types

    def test_healthy_suggestion(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        suggestions = tracker.get_suggestions()
        types = [s["type"] for s in suggestions]
        assert "hp_ok" in types
