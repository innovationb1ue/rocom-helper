"""我方战术动作空间枚举。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.analysis.constants import SDT_TO_TYPE
from src.analysis.pet_identity import same_battle_pet
from src.analysis.skill_resolver import skills_from_pool as resolve_skills_from_pool
from src.analysis.tactical import runtime
from src.data.loader import get_skill_meta


def enumerate_our_actions(
    my_active: Dict[str, Any],
    my_pets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """枚举当前我方可选动作：可用技能 + 可换宠物。"""
    actions: List[Dict[str, Any]] = []
    our_energy = my_active.get("energy", 10)

    equipped = (
        my_active.get("equipped_skills")
        or my_active.get("skills")
        or my_active.get("used_skills")
        or []
    )
    if not equipped:
        equipped = skills_from_pool(my_active)

    for eq in equipped:
        skill_id = eq.get("skill_id")
        if skill_id is None:
            continue
        meta = get_skill_meta(skill_id)
        if meta is None:
            continue

        skill_runtime = runtime.skill_runtime(my_active, skill_id)
        cd_round = runtime.skill_cd_round(eq, skill_runtime)
        if cd_round > 0:
            continue

        energy_cost = runtime.resolve_action_energy_cost(eq, skill_runtime, meta)
        if energy_cost > our_energy:
            continue

        skill_name = eq.get("skill_name") or meta.get("name", "?")
        damage_type = eq.get("skill_damage_type") or meta.get("damage_type", 0)
        element = eq.get("skill_element") or 0
        if element == 0 and meta:
            dam_type = meta.get("skill_dam_type")
            if dam_type is not None:
                element = SDT_TO_TYPE.get(dam_type, 0)

        actions.append({
            "action_type": "skill",
            "skill_id": skill_id,
            "skill_name": skill_name,
            "energy_cost": energy_cost,
            "damage_type": damage_type,
            "skill_element": element,
            "meta": meta,
            "is_damage_skill": damage_type in (2, 3) and (meta.get("dam_para", [0]) or [0])[0] > 0,
            "priority_layer": runtime.skill_priority_layer(eq, skill_runtime, meta),
            "cd_round": cd_round,
        })

    for pet in my_pets:
        if pet.get("current_hp", 1) <= 0:
            continue
        if same_battle_pet(pet, my_active):
            continue
        actions.append({
            "action_type": "switch",
            "switch_to_name": pet.get("name", "?"),
            "switch_to_pet": pet,
            "energy_cost": 0,
        })

    return actions


def skills_from_pool(pet: Dict[str, Any]) -> List[Dict[str, Any]]:
    return resolve_skills_from_pool(pet)
