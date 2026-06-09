"""Runtime skill alignment helpers for damage audit samples."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def runtime_skill_for_sample(
    event: Any,
    target_side: str,
    skill_id: Any,
    breakdown: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], str]:
    for source, state in (("state_before", event.state_before), ("state_after", event.state_after)):
        runtime_skill, pet = find_runtime_skill(state, target_side, skill_id)
        if runtime_skill:
            return runtime_skill, pet, source
    runtime_skill = breakdown.get("runtime_skill")
    if isinstance(runtime_skill, dict) and runtime_skill:
        return runtime_skill, None, "prediction_breakdown"
    return {}, None, "missing"


def find_runtime_skill(
    state: Dict[str, Any],
    target_side: str,
    skill_id: Any,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    if skill_id is None:
        return {}, None
    keys = [str(skill_id), skill_id]
    seen: set[int] = set()
    for pet in attacker_pet_candidates(state, target_side):
        marker = id(pet)
        if marker in seen:
            continue
        seen.add(marker)
        runtime = pet.get("skill_runtime") or {}
        for key in keys:
            item = runtime.get(key)
            if isinstance(item, dict):
                return item, pet
    return {}, None


def attacker_pet_candidates(state: Dict[str, Any], target_side: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    if target_side == "敌方":
        candidate_specs = (("my_active", None), (None, "my_pets"))
    elif target_side == "我方":
        candidate_specs = (("opp_active", None), (None, "opp_pets"))
    else:
        candidate_specs = (
            ("my_active", None), ("opp_active", None),
            (None, "my_pets"), (None, "opp_pets"),
        )
    for active_key, list_key in candidate_specs:
        if active_key:
            pet = state.get(active_key)
            if isinstance(pet, dict):
                candidates.append(pet)
        if list_key:
            candidates.extend([pet for pet in state.get(list_key, []) if isinstance(pet, dict)])
    return candidates


def matched_runtime_value(
    values_by_pet: Dict[Any, Any],
    server_runtime: Dict[str, Any],
    target_pet_id: Any,
) -> Tuple[Optional[str], Any]:
    if not values_by_pet:
        return None, None
    keys: List[str] = []
    for value in (server_runtime.get("matched_target_key"), target_pet_id):
        if value is not None:
            keys.append(str(value))
    for key in dict.fromkeys(keys):
        if values_by_pet.get(key) is not None:
            return key, values_by_pet[key]
    if str(target_pet_id) == "20000000" and len(values_by_pet) == 1:
        key, value = next(iter(values_by_pet.items()))
        return str(key), value
    return None, None
