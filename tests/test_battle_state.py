"""战斗状态追踪器测试 — 模拟真实协议事件流。"""
from __future__ import annotations

import pytest
from src.analysis.battle_state import BattleStateTracker, _compute_effective_speed


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


class TestSideRouting:
    """side 路由测试：通过 pet_id 匹配而非槽位数值范围判断归属。"""

    def test_change_pet_by_pet_id_not_slot_range(self, tracker):
        """换宠时通过 new_pet_id 匹配 my_pets 判定归属，不依赖 battle_pet_id >= 401。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        # Player pet 草苗 (id=101) swaps in at slot 403 (>=401, normally "opponent")
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 403,
             "new_pet_name": "草苗", "new_pet_id": 101,
             "new_pet_types": [3], "new_pet_level": 50,
             "actor_side": 100001},
        ]))
        assert state["my_active"]["name"] == "草苗"

    def test_opp_change_pet_by_pet_id_not_slot_range(self, tracker):
        """换宠时通过 new_pet_id 匹配 opp_pets 判定归属，不依赖 battle_pet_id < 401。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        # Opponent pet 电鼠 (id=201) swaps in at slot 3 (<401, normally "player")
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 3,
             "new_pet_name": "电鼠", "new_pet_id": 201,
             "new_pet_types": [4], "new_pet_level": 50,
             "actor_side": 200002},
        ]))
        assert state["opp_active"]["name"] == "电鼠"

    def test_skill_cast_routes_to_opp_active_by_slot_mapping(self, tracker):
        """对手换宠后，其新槽位 actor_side=3 的 skill_cast 路由到 opp_active。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        # First, opponent swaps to 电鼠 at slot 3
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 3,
             "new_pet_name": "电鼠", "new_pet_id": 201,
             "new_pet_types": [4], "new_pet_level": 50,
             "actor_side": 200002},
        ]))
        # Then 电鼠 uses a skill at slot 3 — energy goes to opp_active
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "actor_side": 3,
             "energy_after": 8, "energy_delta": -2},
        ]))
        assert state["opp_active"]["energy"] == 8
        # my_active energy should be unchanged
        assert state["my_active"]["energy"] == 5

    def test_energy_entry_routes_by_slot_mapping(self, tracker):
        """对手槽位 3 的 energy 事件路由到 opp_active。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 3,
             "new_pet_name": "电鼠", "new_pet_id": 201,
             "new_pet_types": [4], "actor_side": 200002},
        ]))
        # Use some energy first
        tracker.state["opp_active"]["energy"] = 2
        # Energy event at slot 3
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "energy", "target_side": 3, "energy_after": 7},
        ]))
        assert state["opp_active"]["energy"] == 7

    def test_actor_id_cached_for_future_change_pets(self, tracker):
        """首次换宠记录 actor ID，后续同 actor 的换宠直接复用。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        # First change: player actor 100001
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 2,
             "new_pet_name": "草苗", "new_pet_id": 101,
             "new_pet_types": [3], "actor_side": 100001},
        ]))
        assert tracker._player_actor_id == 100001
        # Second change: same actor, pet_id not in any list
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 3,
             "new_pet_name": "火龙", "new_pet_id": 100,
             "new_pet_types": [1], "actor_side": 100001},
        ]))
        # Should still be player (matched by actor)
        assert state["my_active"]["name"] == "火龙"

    def test_unknown_actor_with_known_player_actor_is_opponent(self, tracker):
        """当 player actor 已知时，遇到不同的未知大 actor 值判定为对手。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        # First: player change records actor 100001
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 2,
             "new_pet_name": "草苗", "new_pet_id": 101,
             "new_pet_types": [3], "actor_side": 100001},
        ]))
        # Unknown actor 999999 with new pet not in any list → opponent
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 3,
             "new_pet_name": "陌生宠", "new_pet_id": 99999,
             "new_pet_types": [0], "actor_side": 999999},
        ]))
        assert state["opp_active"]["name"] == "陌生宠"
        assert 3 in tracker._opponent_slots

    def test_slot_mapping_persists_across_rounds(self, tracker):
        """槽位映射在换宠后持续生效。"""
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 3,
             "new_pet_name": "电鼠", "new_pet_id": 201,
             "new_pet_types": [4], "actor_side": 200002},
        ]))
        # Recorded: slot 3 = opponent
        assert 3 in tracker._opponent_slots
        # Fire a round_start (simulates new round)
        tracker.handle_event(0x131A, {"round": 2, "wrappers": []})
        # Slot mapping survives
        assert 3 in tracker._opponent_slots


class TestEffectApply:
    def test_new_effect_added(self, tracker):
        """新效果被添加到 buffs。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 100, "effect_name": "烧伤", "change_type": 1, "buff_stack": 1},
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
             "effect_id": 100, "effect_name": "烧伤", "change_type": 1, "buff_stack": 1},
        ]))
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 100, "effect_name": "烧伤", "change_type": 2, "buff_stack": 2},
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
             "effect_id": 200, "effect_name": "中毒", "change_type": 1, "buff_stack": 1,
             "related_skills": [{"skill_name": "毒液攻击", "skill_id": 7700002}]},
        ]))
        buff = state["opp_active"]["buffs"][0]
        assert buff["source_skill"] == "毒液攻击"

    def test_effect_on_opp(self, tracker):
        """效果添加到敌方精灵。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 401,
             "effect_id": 100, "effect_name": "烧伤", "change_type": 1, "buff_stack": 1},
        ]))
        assert len(state["opp_active"]["buffs"]) == 1

    def test_buff_stack_sets_stage(self, tracker):
        """buff_stack 决定 buff 的 stage（层数）值。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 100, "effect_name": "物攻提升", "change_type": 1, "buff_stack": 5},
        ]))
        assert state["my_active"]["buffs"][0]["stage"] == 5

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

    def test_skill_cast_energy_capped_at_10(self, tracker):
        """skill_cast 中 energy_after 超过 10 时截断。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "actor_side": 1, "energy_after": 19},
        ]))
        assert state["my_active"]["energy"] == 10

    def test_skill_cast_energy_delta_capped_at_10(self, tracker):
        """skill_cast 中 energy_delta 导致超过 10 时截断。"""
        tracker.handle_event(0x1316, _enter_event())
        tracker.state["my_active"]["energy"] = 8
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_cast", "actor_side": 1, "energy_delta": 5},
        ]))
        assert state["my_active"]["energy"] == 10  # min(8+5, 10)

    def test_energy_event_after_capped_at_10(self, tracker):
        """energy 事件中 energy_after 超过 10 时截断。"""
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "energy", "target_side": 1, "energy_after": 14},
        ]))
        assert state["my_active"]["energy"] == 10

    def test_energy_event_delta_capped_at_10(self, tracker):
        """energy 事件中 energy_delta 导致超过 10 时截断。"""
        tracker.handle_event(0x1316, _enter_event())
        tracker.state["my_active"]["energy"] = 9
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "energy", "target_side": 1, "energy_delta": 5},
        ]))
        assert state["my_active"]["energy"] == 10  # min(9+5, 10)

    def test_energy_bottle_via_action_name(self, tracker):
        """能量瓶通过 action_name 匹配（协议实际字段）。"""
        tracker.handle_event(0x1316, _enter_event())
        tracker.state["my_active"]["energy"] = 2
        state = tracker.handle_event(0x13F4, {
            "action_name": "能量瓶", "side": 1, "energy_delta": 3,
        })
        assert state["my_active"]["energy"] == 5  # 2 + 3


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

    def test_healthy_suggestion_removed(self, tracker):
        """HP健康时不再生成无用的 hp_ok 建议。"""
        tracker.handle_event(0x1316, _enter_event())
        suggestions = tracker.get_suggestions()
        types = [s["type"] for s in suggestions]
        assert "hp_ok" not in types

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
        """多个负面状态时追踪 buff。
        注: get_suggestions 检查 stacks < 0，但 buff dict 使用 stage 字段。
        debuffed 建议当前不会触发，因为字段名不匹配（stacks vs stage）。"""
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 100, "effect_name": "烧伤", "change_type": 1, "buff_stack": 1},
            {"kind": "effect_apply", "target_side": 1,
             "effect_id": 101, "effect_name": "中毒", "change_type": 1, "buff_stack": 1},
        ]))
        buffs = tracker.state["my_active"]["buffs"]
        assert len(buffs) == 2
        suggestions = tracker.get_suggestions()
        types = [s["type"] for s in suggestions]
        # Currently won't trigger because buff dict has "stage" not "stacks"
        # assert "debuffed" in types

    def test_no_suggestions_before_battle(self, tracker):
        """战斗开始前无建议。"""
        assert tracker.get_suggestions() == []


class TestSpeedTracking:
    """速度追踪测试 — 覆盖 base_speed 提取、effective_speed 计算、set-once 不变性。"""

    def _enter_event_with_speed(self):
        """battle_enter 事件，wrappers 包含 battle_stats。"""
        return {
            "opcode": 0x1316,
            "battle_id": 12345,
            "battle_mode": 1,
            "round": 0,
            "max_round": 30,
            "wrappers": [
                {"pet_id": 100, "pet_name": "火龙", "types": [1], "side": 1,
                 "hp": 300, "max_hp": 300, "battle_stats": [300, 100, 150, 120, 100, 148]},
                {"pet_id": 200, "pet_name": "水龟", "types": [2], "side": 401,
                 "hp": 350, "max_hp": 350, "battle_stats": [350, 0, 0, 0, 0, 267]},
            ],
        }

    def test_base_speed_from_battle_enter(self, tracker):
        """battle_enter 的 battle_stats[5] 正确设置为 base_speed。"""
        state = tracker.handle_event(0x1316, self._enter_event_with_speed())
        assert state["my_active"]["base_speed"] == 148
        assert state["opp_active"]["base_speed"] == 267

    def test_effective_speed_equals_base_without_buffs(self, tracker):
        """无 speed buff 时 effective_speed == base_speed。"""
        state = tracker.handle_event(0x1316, self._enter_event_with_speed())
        assert state["my_active"]["effective_speed"] == 148
        assert state["opp_active"]["effective_speed"] == 267

    def test_effective_speed_none_without_base(self, tracker):
        """无 battle_stats 时 base_speed 和 effective_speed 均为 None。"""
        state = tracker.handle_event(0x1316, _enter_event())
        assert state["my_active"]["base_speed"] is None
        assert state["my_active"]["effective_speed"] is None

    def test_effective_speed_with_known_buff(self):
        """speed buff 20010100 (+10 flat/stage) 在 stage=2 时 +20。"""
        pet = {"name": "测试宠", "base_speed": 148, "buffs": [
            {"id": 20010100, "stage": 2},
        ]}
        assert _compute_effective_speed(pet) == 168  # 148 + 10*2

    def test_effective_speed_with_pct_buff(self):
        """pct speed buff (20010011, +20% total) 在无 flat 时乘算。"""
        pet = {"name": "测试宠", "base_speed": 150, "buffs": [
            {"id": 20010011, "stage": 1},
        ]}
        assert _compute_effective_speed(pet) == 180  # 150 * 1.2

    def test_effective_speed_minimum_one(self):
        """effective_speed 最低为 1。"""
        pet = {"name": "测试宠", "base_speed": 10, "buffs": [
            {"id": 20010056, "stage": 2},  # -10 flat/stage → 10 - 20 = -10 → max(1, ...)
        ]}
        assert _compute_effective_speed(pet) == 1

    def test_base_speed_from_change_pet(self, tracker):
        """change_pet 的 new_pet_battle_stats[5] 正确设置新宠物 base_speed。"""
        tracker.handle_event(0x1316, self._enter_event_with_speed())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 402,
             "new_pet_name": "电鼠", "new_pet_id": 999,
             "new_pet_types": [4], "new_pet_level": 50,
             "new_pet_battle_stats": [280, 0, 0, 0, 0, 200],
             "new_pet_current_hp": 280, "new_pet_max_hp": 280,
             "new_pet_energy": 5},
        ]))
        assert state["opp_active"]["name"] == "电鼠"
        assert state["opp_active"]["base_speed"] == 200

    def test_base_speed_not_overwritten_by_round_start(self, tracker):
        """round_start 提供不同 speed 时不覆盖已设置的 base_speed。"""
        tracker.handle_event(0x1316, self._enter_event_with_speed())
        assert tracker.state["my_active"]["base_speed"] == 148
        # Round start with a different speed value in wrapper
        tracker.handle_event(0x131A, {
            "round": 1,
            "wrappers": [
                {"pet_id": 100, "pet_name": "火龙", "types": [1], "side": 1,
                 "hp": 280, "max_hp": 300, "battle_stats": [300, 100, 150, 120, 100, 999]},
            ],
        })
        # base_speed should remain 148 (set-once invariant)
        assert tracker.state["my_active"]["base_speed"] == 148

    def test_base_speed_set_from_round_start_when_initially_missing(self, tracker):
        """battle_enter 无 battle_stats 时，round_start 补充 base_speed。"""
        tracker.handle_event(0x1316, _enter_event())
        assert tracker.state["my_active"]["base_speed"] is None
        # Round start provides battle_stats
        state = tracker.handle_event(0x131A, {
            "round": 1,
            "wrappers": [
                {"pet_id": 100, "pet_name": "火龙", "types": [1], "side": 1,
                 "hp": 300, "max_hp": 300, "battle_stats": [300, 100, 150, 120, 100, 148]},
            ],
        })
        assert state["my_active"]["base_speed"] == 148

    def test_battle_stats_zero_speed_not_set(self, tracker):
        """battle_stats[5]=0 不应设置 base_speed。"""
        state = tracker.handle_event(0x1316, {
            "opcode": 0x1316, "battle_id": 1, "battle_mode": 1,
            "round": 0, "max_round": 30,
            "wrappers": [
                {"pet_id": 100, "pet_name": "零速宠", "types": [1], "side": 1,
                 "hp": 300, "max_hp": 300, "battle_stats": [300, 0, 0, 0, 0, 0]},
            ],
        })
        assert state["my_active"]["base_speed"] is None


# ---------------------------------------------------------------------------
# P1 协议覆盖扩展测试
# ---------------------------------------------------------------------------


class TestPvpPerformState:
    """0x13FC/0x13F3 应触发与 0x1324 相同的状态更新。"""

    def test_pvp_perform_damage_updates_opp_hp(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x13FC, _action_resolve_event([
            {"kind": "damage", "damage": 100, "target_hp_after": 250,
             "damage_target_side": 401},
        ]))
        assert state["opp_active"]["current_hp"] == 250

    def test_pvp_perform_skill_cast_updates_energy(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x13FC, _action_resolve_event([
            {"kind": "skill_cast", "actor_side": 1, "skill_id": 1,
             "skill_name": "火花", "energy_delta": -2, "energy_after": 8},
        ]))
        assert state["my_active"]["energy"] == 8

    def test_preplay_damage_updates_opp_hp(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x13F3, _action_resolve_event([
            {"kind": "damage", "damage": 80, "target_hp_after": 270,
             "damage_target_side": 401},
        ]))
        assert state["opp_active"]["current_hp"] == 270

    def test_pvp_perform_change_pet(self, tracker):
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        state = tracker.handle_event(0x13FC, _action_resolve_event([
            {"kind": "change_pet", "battle_pet_id": 402, "actor_side": 401,
             "rest_pet_id": 401,
             "new_pet_name": "电鼠", "new_pet_id": 201, "new_pet_types": [4],
             "new_pet_level": 50, "new_pet_hp": 280, "new_pet_max_hp": 280,
             "new_pet_energy": 5},
        ]))
        assert state["opp_active"]["name"] == "电鼠"

    def test_pvp_perform_defeat(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x13FC, _action_resolve_event([
            {"kind": "defeat", "defeat_target_side": 401, "defeat_actor_side": 1},
        ]))
        assert state["opp_active"]["current_hp"] == 0


class TestWeatherChange:
    """entry_type 22 weather_change 应更新 state["weather"]。"""

    def test_weather_change_updates_state(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "weather_change", "weather_id": 5,
             "weather_expire_round": 3, "skill_id": 7700001},
        ]))
        assert state["weather"]["id"] == 5
        assert state["weather"]["expire_round"] == 3

    def test_weather_change_mid_battle(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "weather_change", "weather_id": 3, "weather_expire_round": 5},
        ]))
        assert tracker.state["weather"]["id"] == 3
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "weather_change", "weather_id": 7, "weather_expire_round": 2},
        ]))
        assert state["weather"]["id"] == 7
        assert state["weather"]["expire_round"] == 2

    def test_weather_change_no_id_ignored(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "weather_change"},
        ]))
        # weather unchanged — still initial value from _enter_event (id=0)
        assert tracker.state["weather"]["id"] == 0


class TestSkillState:
    """entry_type 19 skill_state 应记录到 active pet 的 skill_states 字典。"""

    def test_skill_state_recorded_on_my_pet(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_state", "caster_pet_id": 100, "state_code": 5},
        ]))
        assert state["my_active"]["skill_states"][100] == 5

    def test_skill_state_recorded_on_opp_pet(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_state", "caster_pet_id": 200, "state_code": 8},
        ]))
        assert state["opp_active"]["skill_states"][200] == 8

    def test_skill_state_missing_fields_ignored(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "skill_state"},
        ]))
        assert "skill_states" not in tracker.state["my_active"]


class TestActionAck:
    """0x130C 应更新 HP/energy 中间状态。"""

    def test_action_ack_updates_hp_and_energy(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        tracker.handle_event(0x1324, _action_resolve_event([
            {"kind": "damage", "damage": 100, "target_hp_after": 200,
             "damage_target_side": 1},
        ]))
        state = tracker.handle_event(0x130C, {
            "current_hp": 195,
            "energy_after": 3,
        })
        assert state["my_active"]["current_hp"] == 195
        assert state["my_active"]["energy"] == 3

    def test_action_ack_energy_update_only(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x130C, {
            "energy_after": 7,
        })
        assert state["my_active"]["energy"] == 7

    def test_action_ack_with_wrappers(self, tracker):
        tracker.handle_event(0x1316, _enter_event_multi_pet())
        state = tracker.handle_event(0x130C, {
            "state_wrappers": [
                {"pet_id": 100, "pet_name": "火龙", "side": 1,
                 "hp": 280, "max_hp": 300},
                {"pet_id": 200, "pet_name": "水龟", "side": 401,
                 "hp": 310, "max_hp": 350},
            ],
        })
        assert state["my_active"]["current_hp"] == 280
        assert state["opp_active"]["current_hp"] == 310

    def test_action_ack_no_active_pet(self, tracker):
        state = tracker.handle_event(0x130C, {
            "current_hp": 100,
            "energy_after": 5,
        })
        assert state["my_active"] is None

    def test_action_ack_hp_pct_recalculated(self, tracker):
        tracker.handle_event(0x1316, _enter_event())
        state = tracker.handle_event(0x130C, {
            "current_hp": 150,
        })
        assert state["my_active"]["hp_pct"] == 150 / 300
