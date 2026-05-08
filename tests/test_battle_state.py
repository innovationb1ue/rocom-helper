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


def _enter_event_multi_pet():
    """多宠物战斗：我方2只，敌方3只。side=1 全部我方，side=401 全部敌方。"""
    return {
        "opcode": 0x1316,
        "battle_id": 99999,
        "battle_mode": 1,
        "round": 0,
        "max_round": 30,
        "wrappers": [
            {"pet_id": 100, "pet_name": "火龙", "types": [1], "side": 1,
             "slot": 1, "hp": 300, "max_hp": 300},
            {"pet_id": 101, "pet_name": "草苗", "types": [3], "side": 1,
             "slot": 2, "hp": 250, "max_hp": 250},
            {"pet_id": 200, "pet_name": "水龟", "types": [2], "side": 401,
             "slot": 401, "hp": 350, "max_hp": 350},
            {"pet_id": 201, "pet_name": "电鼠", "types": [4], "side": 401,
             "slot": 402, "hp": 280, "max_hp": 280},
            {"pet_id": 202, "pet_name": "冰狐", "types": [5], "side": 401,
             "slot": 403, "hp": 260, "max_hp": 260},
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

    def test_multi_pet_roster(self, tracker):
        state = tracker.handle_event(0x1316, _enter_event_multi_pet())
        assert len(state["my_pets"]) == 2
        assert len(state["opp_pets"]) == 3


class TestDamageTracking:
    def test_damage_applied(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 100, "target_hp_after": 250,
             "damage_target_side": 401},
        ]))
        assert state["opp_active"]["current_hp"] == 250
        assert state["opp_active"]["hp_pct"] < 1.0

    def test_damage_to_self(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 50, "target_hp_after": 250,
             "damage_target_side": 1},
        ]))
        assert state["my_active"]["current_hp"] == 250

    def test_damage_with_string_side(self, tracker):
        """字符串 side 值也应正确识别。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 50, "target_hp_after": 250,
             "damage_target_side": "我方"},
        ]))
        assert state["my_active"]["current_hp"] == 250

    def test_cumulative_damage(self, tracker):
        """多轮伤害累积正确。"""
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 100, "target_hp_after": 250,
             "damage_target_side": 401},
        ]))
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 80, "target_hp_after": 170,
             "damage_target_side": 401},
        ]))
        assert state["opp_active"]["current_hp"] == 170


class TestSkillCast:
    def test_energy_consumed(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "skill_id": 7700001, "skill_name": "愿力冲击",
             "actor_side": 1, "energy_delta": -2, "energy_after": 3},
        ]))
        assert state["my_active"]["energy"] == 3

    def test_skill_recorded_in_used_skills(self, tracker):
        """使用过的技能被记录。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "skill_id": 7700001, "skill_name": "愿力冲击",
             "actor_side": 1, "energy_after": 3},
        ]))
        used = state["my_active"].get("used_skills", [])
        assert any(s.get("skill_id") == 7700001 for s in used)

    def test_skill_not_duplicated(self, tracker):
        """同一技能多次使用不重复记录。"""
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "skill_id": 7700001, "skill_name": "愿力冲击",
             "actor_side": 1, "energy_after": 3},
        ]))
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "skill_id": 7700001, "skill_name": "愿力冲击",
             "actor_side": 1, "energy_after": 2},
        ]))
        used = state["my_active"].get("used_skills", [])
        assert sum(1 for s in used if s.get("skill_id") == 7700001) == 1


class TestDefeatEvent:
    def test_defeat_sets_hp_zero(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "defeat", "target_side": 401},
        ]))
        assert state["opp_active"]["current_hp"] == 0
        assert state["opp_active"]["hp_pct"] == 0.0


class TestChangePet:
    def test_my_pet_switch(self, tracker):
        """我方换宠：my_active 更新。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 2,
             "new_pet_name": "草苗", "new_pet_id": 101,
             "new_pet_types": [3], "new_pet_level": 50},
        ]))
        assert state["my_active"]["name"] == "草苗"

    def test_opp_pet_switch(self, tracker):
        """敌方换宠：opp_active 更新。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 402,
             "new_pet_name": "电鼠", "new_pet_id": 201,
             "new_pet_types": [4], "new_pet_level": 50},
        ]))
        assert state["opp_active"]["name"] == "电鼠"

    def test_prev_active_name_recorded(self, tracker):
        """换宠记录 _prev_active_name。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 2,
             "new_pet_name": "草苗", "new_pet_id": 101,
             "new_pet_types": [3]},
        ]))
        entries = state["events"][-1].get("entries", [])
        # The change_pet entry should have _prev_active_name
        entry = entries[0] if entries else {}
        assert entry.get("_prev_active_name") == "火龙"

    def test_switch_to_unknown_pet_creates_entry(self, tracker):
        """换宠时遇到未知宠物 → 自动创建。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 402,
             "new_pet_name": "神秘宠", "new_pet_id": 999,
             "new_pet_types": [0], "new_pet_level": 50},
        ]))
        assert state["opp_active"]["name"] == "神秘宠"
        assert len(state["opp_pets"]) == 2

    def test_switch_clears_buffs(self, tracker):
        """换宠时清除 buffs。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        # Apply a buff first
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 100, "effect_name": "烧伤"},
        ]))
        assert len(tracker.state["my_active"]["buffs"]) == 1
        # Switch pet
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 2,
             "new_pet_name": "草苗", "new_pet_id": 101,
             "new_pet_types": [3]},
        ]))
        assert state["my_active"]["name"] == "草苗"
        assert state["my_active"]["buffs"] == []


class TestEffectApply:
    def test_new_effect_added(self, tracker):
        """新效果被添加到 buffs。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 100, "effect_name": "烧伤", "effect_stage": 1},
        ]))
        buffs = state["my_active"]["buffs"]
        assert len(buffs) == 1
        assert buffs[0]["name"] == "烧伤"
        assert buffs[0]["id"] == 100

    def test_existing_effect_updated(self, tracker):
        """重复效果更新 stage 和 turns_applied。"""
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 100, "effect_name": "烧伤", "effect_stage": 1},
        ]))
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 100, "effect_name": "烧伤", "effect_stage": 2},
        ]))
        buffs = state["my_active"]["buffs"]
        assert len(buffs) == 1  # Not duplicated
        assert buffs[0]["stage"] == 2
        assert buffs[0]["turns_applied"] == 2

    def test_effect_with_source_skill(self, tracker):
        """效果记录来源技能。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 401,
             "effect_id": 200, "effect_name": "中毒", "effect_stage": 1,
             "related_skills": [{"skill_name": "毒液攻击", "skill_id": 7700002}]},
        ]))
        buff = state["opp_active"]["buffs"][0]
        assert buff["source_skill"] == "毒液攻击"

    def test_effect_on_opp(self, tracker):
        """效果添加到敌方精灵。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 401,
             "effect_id": 100, "effect_name": "烧伤", "effect_stage": 1},
        ]))
        assert len(state["opp_active"]["buffs"]) == 1

    def test_effect_stage_update(self, tracker):
        """effect_stage 类型事件更新已有 buff 的 stage。"""
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 100, "effect_name": "烧伤", "effect_stage": 1},
        ]))
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_stage", "actor_side": 1,
             "effect_id": 100, "effect_stage": 3},
        ]))
        assert state["my_active"]["buffs"][0]["stage"] == 3


class TestHeal:
    def test_hp_restored(self, tracker):
        """治疗恢复 HP。"""
        tracker.handle_event(0x1316, _enter_event())
        # First damage
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 100, "target_hp_after": 200,
             "damage_target_side": 1},
        ]))
        assert tracker.state["my_active"]["current_hp"] == 200
        # Then heal
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "heal", "target_side": 1, "target_hp_after": 280},
        ]))
        assert state["my_active"]["current_hp"] == 280
        assert state["my_active"]["hp_pct"] == pytest.approx(280 / 300)


class TestEnergyRecovery:
    def test_energy_recovery(self, tracker):
        """能量恢复。"""
        tracker.handle_event(0x1316, _enter_event())
        # Use energy
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "actor_side": 1, "energy_after": 3},
        ]))
        assert tracker.state["my_active"]["energy"] == 3
        # Recover energy
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "energy", "target_side": 1, "energy_after": 8},
        ]))
        assert state["my_active"]["energy"] == 8

    def test_energy_delta(self, tracker):
        """能量变化通过 delta 更新。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "energy", "target_side": 1, "energy_delta": 2},
        ]))
        assert state["my_active"]["energy"] == 7  # 5 + 2


class TestSpecialRefresh:
    def test_energy_bottle(self, tracker):
        """能量瓶恢复能量。"""
        tracker.handle_event(0x1316, _enter_event())
        # Use some energy first
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "actor_side": 1, "energy_after": 2},
        ]))
        # Use energy bottle
        state = tracker.handle_event(0x13F4, {
            "kind": "energy_bottle", "side": 1, "energy_delta": 3,
        })
        assert state["my_active"]["energy"] == 5  # 2 + 3

    def test_energy_bottle_capped_at_10(self, tracker):
        """能量瓶上限 10。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x13F4, {
            "kind": "energy_bottle", "side": 1, "energy_delta": 10,
        })
        assert state["my_active"]["energy"] == 10  # min(5+10, 10)


class TestBattleReset:
    def test_second_battle_resets_state(self, tracker):
        """第二次进入战斗时状态完全重置。"""
        # First battle
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 100, "target_hp_after": 200,
             "damage_target_side": 1},
        ]))
        tracker.handle_event(0x132C, _finish_event("WIN"))
        # Second battle
        state = tracker.handle_event(0x1316, _enter_event())
        assert state["result"] is None
        assert state["round"] == 0
        assert state["my_active"]["current_hp"] == 300
        assert state["my_active"]["max_hp"] == 300
        assert state["my_active"]["hp_pct"] == 1.0
        assert state["phase"] == "selecting"


class TestDefeatAndReplacement:
    def test_defeat_then_switch(self, tracker):
        """击败后换上新宠物。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        # Defeat opponent's active pet
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "defeat", "target_side": 401},
        ]))
        assert tracker.state["opp_active"]["current_hp"] == 0
        # Opponent switches
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 402,
             "new_pet_name": "电鼠", "new_pet_id": 201,
             "new_pet_types": [4]},
        ]))
        assert state["opp_active"]["name"] == "电鼠"


class TestBattleFinish:
    def test_result_recorded(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x132C, _finish_event("WIN"))
        assert state["result"] == "WIN"

    def test_hp_updated_on_finish(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x132C, _finish_event("WIN"))
        assert state["my_pets"][0]["current_hp"] == 200
        assert state["opp_pets"][0]["current_hp"] == 0

    def test_phase_finished(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x132C, _finish_event("WIN"))
        assert state["phase"] == "finished"


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
             "actor_side": 1, "energy_delta": -2, "energy_after": 3},
        ]))
        assert state["my_active"]["energy"] == 3

        # 4. Damage
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 120, "target_hp_after": 230,
             "damage_target_side": 401},
        ]))
        assert state["opp_active"]["current_hp"] == 230

        # 5. Battle finish
        state = tracker.handle_event(0x132C, _finish_event("WIN"))
        assert state["result"] == "WIN"
        assert len(state["events"]) >= 4


class TestSuggestions:
    def test_low_hp_suggestion(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 250, "target_hp_after": 50,
             "damage_target_side": 1},
        ]))
        suggestions = tracker.get_suggestions()
        types = [s["type"] for s in suggestions]
        assert "low_hp" in types

    def test_healthy_suggestion(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        suggestions = tracker.get_suggestions()
        types = [s["type"] for s in suggestions]
        assert "hp_ok" in types

    def test_finish_off_suggestion(self, tracker):
        """对手低血量时出现 finish_off 建议。"""
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 300, "target_hp_after": 50,
             "damage_target_side": 401},
        ]))
        suggestions = tracker.get_suggestions()
        types = [s["type"] for s in suggestions]
        assert "finish_off" in types

    def test_low_energy_suggestion(self, tracker):
        """能量不足时出现 low_energy 建议。"""
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "actor_side": 1, "energy_after": 1},
        ]))
        suggestions = tracker.get_suggestions()
        types = [s["type"] for s in suggestions]
        assert "low_energy" in types

    def test_debuffed_suggestion(self, tracker):
        """多个负面状态时出现 debuffed 建议。"""
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 100, "effect_name": "烧伤", "effect_stage": -1},
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 101, "effect_name": "中毒", "effect_stage": -1},
        ]))
        suggestions = tracker.get_suggestions()
        types = [s["type"] for s in suggestions]
        assert "debuffed" in types

    def test_no_suggestions_before_battle(self, tracker):
        """战斗开始前无建议。"""
        assert tracker.get_suggestions() == []
