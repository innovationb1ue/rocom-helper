"""换宠状态投影测试。"""
from __future__ import annotations

from src.analysis.projection.pets import project_change_pet


def test_project_change_pet_matches_player_slot_fallback():
    second_pet = {"name": "二号", "pet_id": 2}
    state = {
        "my_active": {"name": "一号"},
        "my_pets": [{"name": "一号", "pet_id": 1}, second_pet],
    }

    project_change_pet(state, {"battle_pet_id": 2})

    assert state["my_active"] is second_pet
    assert second_pet["side"] == 1
    assert second_pet["slot"] == 2
    assert second_pet.get("battle_uid")


def test_project_change_pet_prefers_materialized_base_conf_match():
    placeholder = {"name": "未知", "pet_id": 20000000, "base_conf_id": 10}
    materialized = {
        "name": "真实",
        "pet_id": 20000000,
        "base_conf_id": 10,
        "stats": [{"name": "ATK"}],
    }
    state = {
        "opp_active": placeholder,
        "opp_pets": [placeholder, materialized],
    }

    project_change_pet(
        state,
        {"battle_pet_id": 401, "target_side": 401, "new_pet_base_conf_id": 10},
    )

    assert state["opp_active"] is materialized

