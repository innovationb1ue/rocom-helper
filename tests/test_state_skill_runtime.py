"""Skill runtime state helper tests."""
from __future__ import annotations

from src.analysis.battle_state import BattleStateTracker
from src.analysis.state import skill_runtime


def test_update_skill_runtime_merges_skill_data_and_updates_equipped_skill():
    tracker = BattleStateTracker()
    tracker.state["round"] = 8
    pet = {
        "equipped_skills": [
            {"skill_id": 7120090, "skill_name": "毒囊"},
        ],
    }

    skill_runtime.update_skill_runtime(tracker, pet, {
        "skill_id": 7120090,
        "skill_data": {"cost_energy": 3, "state": 1},
        "cost_energy_result": 2,
        "damage_params": [{"pet_id": 401, "damage_param": 150}],
        "restraint_types": [{"pet_id": 401, "restraint_type": -1}],
        "source": "skill_sync",
    })

    runtime = pet["skill_runtime"]["7120090"]
    assert runtime["skill_id"] == 7120090
    assert runtime["cost_energy"] == 3
    assert runtime["cost_energy_result"] == 2
    assert runtime["damage_params_by_pet"] == {"401": 150}
    assert runtime["restraint_types_by_pet"] == {"401": -1}
    assert runtime["round"] == 8
    assert pet["equipped_skills"][0]["runtime_cost_energy"] == 2
    assert pet["equipped_skills"][0]["runtime_damage_params"] == [
        {"pet_id": 401, "damage_param": 150},
    ]


def test_normalize_battle_skill_pool_filters_internal_and_duplicates():
    pet = {"equipped_skills": [{"skill_id": 7120090}]}
    skills = [
        {"skill_id": 7000010, "source_index": 0},
        {"skill_id": 7120090, "source_index": 1},
        {"skill_id": 7120100, "source_index": 2},
        {"skill_id": 7120100, "source_index": 3},
    ]

    normalized = skill_runtime.normalize_battle_skill_pool(pet, skills)

    assert [item["skill_id"] for item in normalized] == [7120090, 7120100]
    assert [item["pool_index"] for item in normalized] == [0, 1]


def test_apply_battle_skill_pool_updates_leader_pool_when_expanded():
    pet = {"equipped_skills": [{"skill_id": 7120090}]}
    skills = [
        {"skill_id": 7120090, "source_index": 0},
        {"skill_id": 7120100, "source_index": 1},
    ]

    skill_runtime.apply_battle_skill_pool(pet, skills, source="test")

    assert [item["skill_id"] for item in pet["skills"]] == [7120090, 7120100]
    assert pet["battle_skill_pool_source"] == "test"
    assert [item["skill_id"] for item in pet["leader_skill_pool"]] == [7120090, 7120100]
    assert pet["leader_skill_pool_source"] == "test"
