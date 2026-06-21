"""Battle REST response projection helpers."""
from __future__ import annotations

from typing import Any, Dict


def battle_pets_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    """构建 `/api/battle/pets` 响应。"""
    return {
        "my_pets": state.get("my_pets", []),
        "opp_pets": state.get("opp_pets", []),
        "my_active": state.get("my_active"),
        "opp_active": state.get("opp_active"),
    }


def _pet_buffs_payload(pet: Dict[str, Any]) -> Dict[str, Any]:
    return {"pet_name": pet.get("name"), "buffs": pet.get("buffs", [])}


def battle_effects_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    """构建 `/api/battle/effects` 响应。"""
    return {
        "weather": state.get("weather"),
        "phase": state.get("phase"),
        "my_buffs": [_pet_buffs_payload(pet) for pet in state.get("my_pets", [])],
        "opp_buffs": [_pet_buffs_payload(pet) for pet in state.get("opp_pets", [])],
    }
