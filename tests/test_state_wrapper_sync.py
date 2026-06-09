"""Wrapper 同步 helper 的直接单元测试。"""
from __future__ import annotations

from src.analysis.battle_state import BattleStateTracker
from src.analysis.constants import OPCODE_ACTION_ACK
from src.analysis.state import wrapper_sync


def _tracker_with_pet() -> tuple[BattleStateTracker, dict]:
    tracker = BattleStateTracker()
    pet = {
        "pet_id": 100,
        "slot": 1,
        "side": 1,
        "name": "我方宠",
        "current_hp": 300,
        "max_hp": 300,
        "energy": 6,
        "buffs": [{"id": 1, "stage": 1}],
        "equipped_skills": [],
        "stats": [1, 2],
    }
    tracker.state["my_pets"] = [pet]
    tracker.state["my_active"] = pet
    tracker._bind_battle_side(1, pet, is_mine=True)
    return tracker, pet


def test_pet_matches_uses_slot_for_hidden_opponent_ids():
    pet = {"pet_id": 20000000, "slot": 401, "name": "白发路路"}

    assert wrapper_sync.pet_matches(pet, {"pet_id": 20000000, "slot": 401, "name": "火神"})
    assert not wrapper_sync.pet_matches(pet, {"pet_id": 20000000, "slot": 402, "name": "火神"})


def test_update_pets_from_wrappers_merges_runtime_fields_and_active_pointer():
    tracker, pet = _tracker_with_pet()

    wrapper_sync.update_pets_from_wrappers(tracker, [{
        "side": 1,
        "pet_id": 100,
        "slot": 1,
        "name": "我方宠改名",
        "hp": 250,
        "max_hp": 320,
        "energy": 9,
        "base_conf_id": 10001,
        "base_skill_pool": [1, 2],
        "battle_stats": [320, 1, 2, 3, 4, 188],
        "initial_buffs": [{"id": 1, "stage": 1}, {"id": 2, "stage": 1}],
        "equipped_skills": [{"skill_id": 7020370}],
        "skills": [{"skill_id": 7020370}],
        "types": ["毒"],
        "passive_skill_id": 9001,
    }])

    assert tracker.state["my_active"] is pet
    assert pet["name"] == "我方宠改名"
    assert pet["current_hp"] == 250
    assert pet["max_hp"] == 320
    assert pet["energy"] == 9
    assert pet["base_speed"] == 188
    assert pet["base_conf_id"] == 10001
    assert pet["base_skill_pool"] == [1, 2]
    assert pet["equipped_skills"] == [{"skill_id": 7020370}]
    assert pet["skills"] == [{"skill_id": 7020370}]
    assert pet["types"] == ["毒"]
    assert pet["innate_skill_id"] == 9001
    assert [buff["id"] for buff in pet["buffs"]] == [1, 2]


def test_update_pets_from_wrappers_creates_new_pet_and_applies_ack_skill_pool():
    tracker = BattleStateTracker()
    tracker._current_opcode = OPCODE_ACTION_ACK

    wrapper_sync.update_pets_from_wrappers(tracker, [{
        "side": 1,
        "pet_id": 101,
        "slot": 2,
        "name": "新宠",
        "hp": 200,
        "max_hp": 200,
        "skills": [{"skill_id": 7020370}, {"skill_id": 7110200}],
    }])

    assert len(tracker.state["my_pets"]) == 1
    pet = tracker.state["my_pets"][0]
    assert tracker.state["my_active"] is pet
    assert pet["name"] == "新宠"
    assert [skill["skill_id"] for skill in pet["battle_skill_pool"]] == [7020370, 7110200]
    assert pet["battle_skill_pool_source"] == "action_ack.state_wrapper.skill_round_data"
