"""Side and active-pet resolver helper tests."""
from __future__ import annotations

from src.analysis.battle_state import BattleStateTracker
from src.analysis.state import side_resolver


def _tracker_with_sides() -> tuple[BattleStateTracker, dict, dict]:
    tracker = BattleStateTracker()
    my_pet = {"pet_id": 100, "slot": 1, "name": "火龙", "current_hp": 300, "max_hp": 300}
    opp_pet = {"pet_id": 200, "slot": 401, "name": "水龟", "current_hp": 350, "max_hp": 350}
    tracker.state["my_pets"] = [my_pet]
    tracker.state["opp_pets"] = [opp_pet]
    tracker.state["my_active"] = my_pet
    tracker.state["opp_active"] = opp_pet
    side_resolver.bind_battle_side(tracker, 1, my_pet, is_mine=True)
    side_resolver.bind_battle_side(tracker, 401, opp_pet, is_mine=False)
    return tracker, my_pet, opp_pet


def test_is_mine_uses_bound_side_slots_before_numeric_fallback():
    tracker, my_pet, opp_pet = _tracker_with_sides()

    assert side_resolver.is_mine(tracker, 1) is True
    assert side_resolver.is_mine(tracker, 401) is False
    assert tracker._battle_side_pets[1] is my_pet
    assert tracker._battle_side_pets[401] is opp_pet


def test_resolve_pet_for_side_rebinds_fainted_slot_to_living_active():
    tracker, old_pet, new_pet = _tracker_with_sides()
    old_pet["current_hp"] = 0
    living_pet = {"pet_id": 101, "slot": 2, "name": "草苗", "current_hp": 250}
    tracker.state["my_pets"].append(living_pet)
    tracker.state["my_active"] = living_pet

    resolved = side_resolver.resolve_pet_for_side(tracker, 1, bind_fallback=True)

    assert resolved is living_pet
    assert tracker._battle_side_pets[1] is living_pet


def test_pet_for_sync_id_matches_pet_id_slot_and_bound_side():
    tracker, my_pet, opp_pet = _tracker_with_sides()

    assert side_resolver.pet_for_sync_id(tracker, 100) is my_pet
    assert side_resolver.pet_for_sync_id(tracker, 401) is opp_pet
    assert side_resolver.pet_for_sync_id(tracker, "1") is my_pet


def test_pet_name_by_slot_prefers_bound_side_mapping():
    tracker, my_pet, _opp_pet = _tracker_with_sides()
    my_pet["name"] = "绑定名"

    assert side_resolver.pet_name_by_slot(tracker, 1, is_mine=True) == "绑定名"


def test_stable_pet_matches_hidden_ids_by_name():
    pet = {"pet_id": 20000000, "slot": 401, "name": "白发路路"}

    assert side_resolver.stable_pet_matches(pet, {
        "pet_id": 20000000,
        "slot": 401,
        "pet_name": "白发路路",
    })
    assert not side_resolver.stable_pet_matches(pet, {
        "pet_id": 20000000,
        "slot": 402,
        "pet_name": "火神",
    })
