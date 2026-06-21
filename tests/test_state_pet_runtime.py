"""Pet runtime synchronization helper tests."""
from __future__ import annotations

from src.analysis.battle_state import BattleStateTracker
from src.analysis.state import pet_runtime


def _tracker_with_pet() -> tuple[BattleStateTracker, dict]:
    tracker = BattleStateTracker()
    pet = {
        "pet_id": 1,
        "slot": 1,
        "name": "裘卡",
        "current_hp": 300,
        "max_hp": 300,
        "energy": 10,
        "equipped_skills": [{"skill_id": 7020370}],
        "buffs": [],
    }
    tracker.state["round"] = 4
    tracker.state["my_pets"] = [pet]
    tracker.state["my_active"] = pet
    tracker._bind_battle_side(1, pet, is_mine=True)
    return tracker, pet


def test_apply_pet_sync_updates_hp_energy_buff_and_runtime_fields():
    tracker, pet = _tracker_with_pet()

    pet_runtime.apply_pet_sync(tracker, {
        "pet_id": 1,
        "hp_change": -20,
        "hp_result": 280,
        "energy_result": 8,
        "max_energy": 12,
        "shield_result": 5,
        "damage_result": 120,
        "original_damage": 130,
        "charging_skill_id": 7020370,
        "attr_type": 2,
        "attr_change": 1,
        "attr_result": 3,
        "buff_id": 20010020,
        "buff_stack_result": 2,
    })

    assert pet["current_hp"] == 280
    assert pet["energy"] == 8
    assert pet["max_energy"] == 12
    assert pet["shield"] == 5
    assert pet["last_damage_result"] == 120
    assert pet["last_original_damage"] == 130
    assert pet["charging_skill_id"] == 7020370
    assert pet["attr_changes"][-1] == {
        "attr_type": 2,
        "attr_change": 1,
        "attr_result": 3,
        "round": 4,
    }
    assert pet["buffs"][0]["id"] == 20010020
    assert pet["buffs"][0]["stage"] == 2
    assert tracker.state["field_context"]["damage_ledger"][-1]["hp_after"] == 280


def test_apply_pet_info_sync_updates_identity_and_skill_pool():
    tracker, pet = _tracker_with_pet()

    pet_runtime.apply_pet_info_sync(tracker, {
        "pet_id": 1,
        "name": "新裘卡",
        "level": 100,
        "base_conf_id": 10001,
        "types": ["毒"],
        "max_hp": 320,
        "equipped_skills": [{"skill_id": 7020370}],
        "skill_round_data": [
            {"skill_id": 7020370, "source_index": 0},
            {"skill_id": 7020380, "source_index": 1},
        ],
    })

    assert pet["name"] == "新裘卡"
    assert pet["level"] == 100
    assert pet["max_hp"] == 320
    assert pet["runtime_equipped_skills"] == [{"skill_id": 7020370}]
    assert [skill["skill_id"] for skill in pet["battle_skill_pool"]] == [7020370, 7020380]
    assert pet["battle_skill_pool_source"] == "sync_data.pet_info.skill_round_data"


def test_apply_wrapper_runtime_fields_deep_copies_known_fields():
    pet = {}
    wrapper = {
        "state_bits": [1, 2],
        "triggered_buffs": [{"id": 1}],
        "speed_min": 123,
        "ignored": "nope",
    }

    pet_runtime.apply_wrapper_runtime_fields(pet, wrapper)
    wrapper["triggered_buffs"][0]["id"] = 99

    assert pet == {
        "state_bits": [1, 2],
        "triggered_buffs": [{"id": 1}],
        "speed_min": 123,
    }


def test_apply_entry_sync_data_records_history_and_updates_skill_runtime():
    tracker, pet = _tracker_with_pet()
    entry = {
        "kind": "effect_apply",
        "group_id": 7,
        "sync_data": {
            "pet_sync": [{"pet_id": 1, "energy_result": 9}],
            "skill_sync": [{"pet_id": 1, "skill_id": 7020370, "cost_energy_result": 4}],
            "item_sync": [{"item_id": 9001, "num": 1}],
        },
    }

    pet_runtime.apply_entry_sync_data(tracker, entry)

    assert pet["energy"] == 9
    assert pet["skill_runtime"]["7020370"]["cost_energy_result"] == 4
    assert pet["skill_runtime"]["7020370"]["source"] == "skill_sync"
    assert tracker.state["field_context"]["sync_events"][-1]["group_id"] == 7
    assert tracker.state["field_context"]["item_sync_events"][-1]["item_id"] == 9001


def test_apply_pet_skill_updates_uses_data_update_source():
    tracker, pet = _tracker_with_pet()

    pet_runtime.apply_pet_skill_updates(tracker, {
        "pet_skill_updates": [
            {
                "pet_id": 1,
                "skills": [
                    {"skill_id": 7020370, "cost_energy": 3, "source_index": 0},
                    {"skill_id": 7020380, "cost_energy": 5, "source_index": 1},
                ],
            },
        ],
    })

    runtime = pet["skill_runtime"]["7020370"]
    assert runtime["cost_energy"] == 3
    assert runtime["source"] == "data_update.pet_skill"
    assert [skill["skill_id"] for skill in pet["battle_skill_pool"]] == [7020370, 7020380]
    assert pet["battle_skill_pool_source"] == "data_update.pet_skill.skills"
