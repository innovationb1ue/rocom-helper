"""事件格式化模块测试。"""
from __future__ import annotations

import pytest

from src.analysis.battle_processor import compute_battle_summary
from src.analysis.event_formatter import (
    FormattedEvent,
    format_action_entry,
    format_battle_enter,
    format_battle_event,
    format_battle_finish,
    format_round_start,
    format_skill_declare,
    format_skill_select,
    side_label,
)


def _enter_detail():
    return {
        "battle_id": 12345,
        "battle_mode": 1,
        "round": 0,
        "max_round": 30,
        "wrappers": [
            {"pet_id": 100, "pet_name": "火龙", "types": [1], "side": 1,
             "hp": 300, "max_hp": 300},
            {"pet_id": 101, "pet_name": "草苗", "types": [3], "side": 2,
             "hp": 250, "max_hp": 250},
            {"pet_id": 200, "pet_name": "水龟", "types": [2], "side": 401,
             "hp": 350, "max_hp": 350},
            {"pet_id": 201, "pet_name": "电鼠", "types": [4], "side": 402,
             "hp": 280, "max_hp": 280},
        ],
    }


def _state_after_enter():
    return {
        "battle_id": 12345,
        "battle_mode": 1,
        "round": 0,
        "max_round": 30,
        "my_pets": [
            {"pet_id": 100, "name": "火龙", "types": [1], "current_hp": 300,
             "max_hp": 300, "hp_pct": 1.0, "energy": 5, "slot": 1, "side": 1},
            {"pet_id": 101, "name": "草苗", "types": [3], "current_hp": 250,
             "max_hp": 250, "hp_pct": 1.0, "energy": 5, "slot": 2, "side": 2},
        ],
        "opp_pets": [
            {"pet_id": 200, "name": "水龟", "types": [2], "current_hp": 350,
             "max_hp": 350, "hp_pct": 1.0, "energy": 5, "slot": 401, "side": 401},
            {"pet_id": 201, "name": "电鼠", "types": [4], "current_hp": 280,
             "max_hp": 280, "hp_pct": 1.0, "energy": 5, "slot": 402, "side": 402},
        ],
        "my_active": {"pet_id": 100, "name": "火龙", "slot": 1},
        "opp_active": {"pet_id": 200, "name": "水龟", "slot": 401},
        "events": [],
        "result": None,
    }


# ---------------------------------------------------------------------------
# side_label
# ---------------------------------------------------------------------------

class TestSideLabel:
    def test_mine(self):
        assert side_label(1) == "我方"
        assert side_label(3) == "我方"
        assert side_label(6) == "我方"

    def test_opp(self):
        assert side_label(401) == "敌方"
        assert side_label(406) == "敌方"

    def test_none(self):
        assert side_label(None) == "?"


# ---------------------------------------------------------------------------
# format_battle_enter
# ---------------------------------------------------------------------------

class TestFormatBattleEnter:
    def test_summary(self):
        ev = format_battle_enter(_enter_detail(), {})
        assert ev.kind == "battle_enter"
        assert "12345" in ev.summary
        assert ev.color == "green"

    def test_teams(self):
        ev = format_battle_enter(_enter_detail(), {})
        assert len(ev.detail["my_team"]) == 2
        assert len(ev.detail["opp_team"]) == 2
        assert ev.detail["my_team"][0]["name"] == "火龙"
        assert ev.detail["opp_team"][0]["name"] == "水龟"


# ---------------------------------------------------------------------------
# format_round_start
# ---------------------------------------------------------------------------

class TestFormatRoundStart:
    def test_summary(self):
        detail = {"round": 3, "wrappers": []}
        ev = format_round_start(detail, {})
        assert ev.kind == "round_start"
        assert ev.round == 3
        assert "回合 3" in ev.summary

    def test_with_wrappers(self):
        detail = {
            "round": 1,
            "wrappers": [
                {"side": 1, "name": "火龙", "hp": 280, "max_hp": 300, "energy": 3},
                {"side": 401, "name": "水龟", "hp": 350, "max_hp": 350, "energy": 5},
            ],
        }
        ev = format_round_start(detail, {})
        assert len(ev.detail["pet_status"]) == 2
        assert ev.detail["pet_status"][0]["side"] == "我方"


# ---------------------------------------------------------------------------
# format_action_entry — skill_cast
# ---------------------------------------------------------------------------

class TestFormatSkillCast:
    def test_basic(self):
        entry = {
            "kind": "skill_cast",
            "actor_side": 1,
            "skill_name": "愿力冲击",
            "energy_delta": -2,
            "energy_after": 3,
        }
        ev = format_action_entry(entry, _state_after_enter(), round_num=1)
        assert ev.kind == "skill_cast"
        assert "愿力冲击" in ev.summary
        assert "我方" in ev.summary
        assert ev.round == 1

    def test_opp_skill(self):
        entry = {
            "kind": "skill_cast",
            "actor_side": 401,
            "skill_name": "水流喷射",
            "energy_delta": -3,
            "energy_after": 2,
        }
        ev = format_action_entry(entry, _state_after_enter())
        assert "敌方" in ev.summary
        assert "水流喷射" in ev.summary


# ---------------------------------------------------------------------------
# format_action_entry — damage
# ---------------------------------------------------------------------------

class TestFormatDamage:
    def test_basic(self):
        entry = {
            "kind": "damage",
            "damage_target_side": 401,
            "damage": 120,
            "target_hp_after": 230,
            "skill_name": "愿力冲击",
        }
        ev = format_action_entry(entry, _state_after_enter(), round_num=2)
        assert ev.kind == "damage"
        assert "120" in ev.summary
        assert "敌方" in ev.summary
        assert "愿力冲击" in ev.summary
        assert ev.detail["damage"] == 120
        assert ev.detail["hp_after"] == 230

    def test_damage_to_mine(self):
        entry = {
            "kind": "damage",
            "damage_target_side": 1,
            "damage": 80,
            "target_hp_after": 220,
        }
        ev = format_action_entry(entry, _state_after_enter())
        assert "我方" in ev.summary


# ---------------------------------------------------------------------------
# format_action_entry — defeat
# ---------------------------------------------------------------------------

class TestFormatDefeat:
    def test_basic(self):
        entry = {"kind": "defeat", "actor_side": 1, "target_side": 401}
        ev = format_action_entry(entry, _state_after_enter())
        assert ev.kind == "defeat"
        assert "我方" in ev.summary
        assert "敌方" in ev.summary
        assert "击败" in ev.summary
        assert ev.color == "red"


# ---------------------------------------------------------------------------
# format_action_entry — heal
# ---------------------------------------------------------------------------

class TestFormatHeal:
    def test_basic(self):
        entry = {
            "kind": "heal",
            "actor_side": 1,
            "target_side": 1,
            "hp_after": 280,
        }
        ev = format_action_entry(entry, _state_after_enter())
        assert ev.kind == "heal"
        assert "治疗" in ev.summary
        assert "280" in ev.summary
        assert ev.color == "green"


# ---------------------------------------------------------------------------
# format_action_entry — energy
# ---------------------------------------------------------------------------

class TestFormatEnergy:
    def test_basic(self):
        entry = {
            "kind": "energy",
            "actor_side": 1,
            "target_side": 1,
            "energy_delta": 3,
            "energy_after": 8,
        }
        ev = format_action_entry(entry, _state_after_enter())
        assert ev.kind == "energy"
        assert "能量" in ev.summary
        assert ev.detail["energy_after"] == 8


# ---------------------------------------------------------------------------
# format_action_entry — change_pet
# ---------------------------------------------------------------------------

class TestFormatChangePet:
    def test_mine_change(self):
        state = _state_after_enter()
        entry = {
            "kind": "change_pet",
            "actor_side": 99999,
            "battle_pet_id": 2,
            "new_pet_name": "草苗",
            "new_pet_id": 101,
            "_prev_active_name": "火龙",
        }
        ev = format_action_entry(entry, state)
        assert ev.kind == "change_pet"
        assert "我方" in ev.summary
        assert "火龙" in ev.summary
        assert "草苗" in ev.summary

    def test_opp_change(self):
        state = _state_after_enter()
        entry = {
            "kind": "change_pet",
            "actor_side": 4,
            "battle_pet_id": 402,
            "new_pet_name": "电鼠",
            "new_pet_id": 201,
            "_prev_active_name": "水龟",
        }
        ev = format_action_entry(entry, state)
        assert "敌方" in ev.summary
        assert "水龟" in ev.summary
        assert "电鼠" in ev.summary


# ---------------------------------------------------------------------------
# format_action_entry — effect_apply
# ---------------------------------------------------------------------------

class TestFormatEffectApply:
    def test_basic(self):
        entry = {
            "kind": "effect_apply",
            "actor_side": 1,
            "target_side": 401,
            "effect_id": 100,
            "effect_name": "烧伤",
            "change_type": 1,
        }
        ev = format_action_entry(entry, _state_after_enter())
        assert ev.kind == "effect_apply"
        assert "烧伤" in ev.summary

    def test_with_related_skills(self):
        entry = {
            "kind": "effect_apply",
            "actor_side": 1,
            "target_side": 401,
            "effect_name": "中毒",
            "related_skills": [{"skill_name": "毒液攻击", "skill_id": 7700002}],
        }
        ev = format_action_entry(entry, _state_after_enter())
        assert "毒液攻击" in ev.summary


# ---------------------------------------------------------------------------
# format_action_entry — unknown kind
# ---------------------------------------------------------------------------

class TestFormatUnknown:
    def test_unknown_kind(self):
        entry = {"kind": "some_new_kind", "data": 123}
        ev = format_action_entry(entry, _state_after_enter())
        assert ev.kind == "some_new_kind"
        assert ev.color == "gray"

    def test_data_update_suppressed(self):
        entry = {"kind": "data_update", "uin": 12345}
        ev = format_action_entry(entry, _state_after_enter())
        assert ev is None

    def test_pvp_perform_marker(self):
        entry = {"kind": "pvp_perform_marker", "pvp_type": 1}
        ev = format_action_entry(entry, _state_after_enter())
        assert ev.kind == "pvp_perform_marker"
        assert "PVP演出" in ev.summary
        assert ev.color == "purple"

    def test_supply_pet(self):
        entry = {"kind": "supply_pet", "supply_pets": [{"pet_id": 1}, {"pet_id": 2}]}
        ev = format_action_entry(entry, _state_after_enter())
        assert "补宠" in ev.summary
        assert "2只" in ev.summary


# ---------------------------------------------------------------------------
# format_battle_finish
# ---------------------------------------------------------------------------

class TestFormatBattleFinish:
    def test_win(self):
        detail = {
            "result_name": "WIN",
            "rounds": 8,
            "seconds": 195,
            "pvp_score": 32,
            "total_pvp_score": 1250,
        }
        ev = format_battle_finish(detail, _state_after_enter())
        assert ev.kind == "battle_finish"
        assert "WIN" in ev.summary
        assert ev.color == "green"

    def test_lose(self):
        detail = {"result_name": "LOSE", "rounds": 5, "seconds": 120}
        ev = format_battle_finish(detail, _state_after_enter())
        assert ev.color == "red"


# ---------------------------------------------------------------------------
# format_skill_select / format_skill_declare
# ---------------------------------------------------------------------------

class TestFormatSkillSelect:
    def test_with_skill_id(self):
        ev = format_skill_select({"skill_id": 7700001})
        assert "7700001" in ev.summary

    def test_switch(self):
        ev = format_skill_select({"cmd_flag": 2})
        assert "换人" in ev.summary


class TestFormatSkillDeclare:
    def test_with_name(self):
        ev = format_skill_declare({"actor_side": 1, "skill_name": "愿力冲击"})
        assert "愿力冲击" in ev.summary
        assert "我方" in ev.summary


# ---------------------------------------------------------------------------
# format_battle_event (top-level dispatch)
# ---------------------------------------------------------------------------

class TestFormatBattleEvent:
    def test_battle_enter_dispatches(self):
        events = format_battle_event(0x1316, _enter_detail(), {})
        assert len(events) == 1
        assert events[0].kind == "battle_enter"

    def test_action_resolve_multiple_entries(self):
        detail = {
            "entries": [
                {"kind": "skill_cast", "actor_side": 1, "skill_name": "愿力冲击",
                 "energy_delta": -2, "energy_after": 3},
                {"kind": "damage", "damage_target_side": 401, "damage": 100,
                 "target_hp_after": 250},
            ],
        }
        events = format_battle_event(0x1324, detail, _state_after_enter(), round_num=1)
        assert len(events) == 2
        assert events[0].kind == "skill_cast"
        assert events[1].kind == "damage"
        assert events[0].round == 1

    def test_unknown_opcode_returns_empty(self):
        events = format_battle_event(0x9999, {}, {})
        assert events == []


# ---------------------------------------------------------------------------
# compute_battle_summary
# ---------------------------------------------------------------------------

class TestComputeBattleSummary:
    def test_basic(self):
        state = _state_after_enter()
        state["result"] = "WIN"
        state["round"] = 8
        state["events"] = [
            {"opcode": 0x1316}, {"opcode": 0x1316},
            {"opcode": 0x1324}, {"opcode": 0x1324},
        ]
        summary = compute_battle_summary(state)
        assert summary["result"] == "WIN"
        assert summary["rounds"] == 8
        assert len(summary["my_pets_final"]) == 2
        assert len(summary["opp_pets_final"]) == 2
        assert summary["event_stats"]["battle_enter"] == 2

    def test_defeated_pet_status(self):
        state = _state_after_enter()
        state["opp_pets"][0]["current_hp"] = 0
        summary = compute_battle_summary(state)
        assert summary["opp_pets_final"][0]["status"] == "战败"
        assert summary["opp_pets_final"][1]["status"] == "存活"
