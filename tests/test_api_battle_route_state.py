"""Battle REST response projection tests."""
from __future__ import annotations

from src.api.battle_route_state import battle_effects_payload, battle_pets_payload


def test_battle_pets_payload_keeps_contract_fields():
    state = {
        "my_pets": [{"name": "我方"}],
        "opp_pets": [{"name": "敌方"}],
        "my_active": {"name": "我方"},
        "opp_active": {"name": "敌方"},
        "ignored": True,
    }

    assert battle_pets_payload(state) == {
        "my_pets": [{"name": "我方"}],
        "opp_pets": [{"name": "敌方"}],
        "my_active": {"name": "我方"},
        "opp_active": {"name": "敌方"},
    }


def test_battle_effects_payload_collects_pet_buffs():
    state = {
        "weather": {"name": "雨天"},
        "phase": "resolving",
        "my_pets": [{"name": "我方", "buffs": [{"id": 1}]}],
        "opp_pets": [{"name": "敌方"}, {"name": "敌二", "buffs": [{"id": 2}]}],
    }

    assert battle_effects_payload(state) == {
        "weather": {"name": "雨天"},
        "phase": "resolving",
        "my_buffs": [{"pet_name": "我方", "buffs": [{"id": 1}]}],
        "opp_buffs": [
            {"pet_name": "敌方", "buffs": []},
            {"pet_name": "敌二", "buffs": [{"id": 2}]},
        ],
    }


def test_battle_effects_payload_defaults_missing_lists():
    assert battle_effects_payload({}) == {
        "weather": None,
        "phase": None,
        "my_buffs": [],
        "opp_buffs": [],
    }
