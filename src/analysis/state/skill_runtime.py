"""Skill runtime synchronization helpers for BattleStateTracker."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from src.data.loader import get_skill_meta


INTERNAL_LEADER_SKILL_IDS = {280009, 7000010, 7000030}
INTERNAL_LEADER_SKILL_DAM_TYPES = {21}

RUNTIME_SYNC_FIELDS = (
    "skill_name", "damage_param_change", "damage_param_result",
    "damage_param_pet_id", "cast_cnt_change", "cast_cnt_result",
    "pp_change", "pp_result", "cost_energy_change", "cost_energy_result",
    "cost_hp_change", "cost_hp_result", "display_hp_result",
    "sp_energy_skill", "hp_per_energy", "state", "type", "cast_cnt",
    "cost_energy", "raw_cost_energy", "equipped_slot", "cd_round",
    "raw_damage", "rule_energy", "rule_damage_param", "effect_damage_param",
    "buff_damage_param", "ex_damage_param", "damage_params",
    "damage_params_by_pet", "restraint_types", "restraint_types_by_pet",
    "cd_info", "enhance_info", "damage_type", "source",
    "extra_damage_type", "cr_damage_params", "skill_buff",
    "trans_info", "set_cost_info",
)


def skill_runtime_key(skill_id: Any) -> str:
    return str(skill_id)


def update_skill_runtime(tracker: Any, pet: Optional[Dict[str, Any]], sync: Dict[str, Any]) -> None:
    if pet is None or sync.get("skill_id") is None:
        return
    skill_id = sync["skill_id"]
    runtime = pet.setdefault("skill_runtime", {})
    item = runtime.setdefault(skill_runtime_key(skill_id), {"skill_id": skill_id})
    merged = dict(sync.get("skill_data") or {})
    merged.update({k: v for k, v in sync.items() if k != "skill_data"})
    if merged.get("damage_params"):
        merged["damage_params_by_pet"] = {
            str(dp.get("pet_id")): dp.get("damage_param")
            for dp in merged["damage_params"]
            if dp.get("pet_id") is not None and dp.get("damage_param") is not None
        }
    if merged.get("restraint_types"):
        merged["restraint_types_by_pet"] = {
            str(rt.get("pet_id")): rt.get("restraint_type")
            for rt in merged["restraint_types"]
            if rt.get("pet_id") is not None and rt.get("restraint_type") is not None
        }
    for key in RUNTIME_SYNC_FIELDS:
        if merged.get(key) is not None:
            item[key] = merged[key]
    item["source_round"] = tracker.state.get("round", 0)
    item["round"] = tracker.state.get("round", 0)

    runtime_cost = (
        merged.get("cost_energy_result")
        if merged.get("cost_energy_result") is not None
        else merged.get("cost_energy")
    )
    if runtime_cost is None:
        runtime_cost = merged.get("raw_cost_energy")

    # Keep equipped skills current so same-round advice sees server sync data.
    for skill in pet.get("equipped_skills", []):
        if skill.get("skill_id") != skill_id:
            continue
        if runtime_cost is not None:
            skill["runtime_cost_energy"] = runtime_cost
        if merged.get("damage_params") is not None:
            skill["runtime_damage_params"] = merged["damage_params"]
        if merged.get("restraint_types") is not None:
            skill["runtime_restraint_types"] = merged["restraint_types"]


def skill_dam_type(skill: Dict[str, Any]) -> Optional[int]:
    value = skill.get("skill_dam_type")
    if value is not None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    meta = get_skill_meta(skill.get("skill_id"))
    if isinstance(meta, dict) and meta.get("skill_dam_type") is not None:
        try:
            return int(meta["skill_dam_type"])
        except (TypeError, ValueError):
            return None
    return None


def is_internal_leader_skill(skill: Dict[str, Any]) -> bool:
    try:
        skill_id = int(skill.get("skill_id"))
    except (TypeError, ValueError):
        return True
    if skill_id in INTERNAL_LEADER_SKILL_IDS:
        return True
    return skill_dam_type(skill) in INTERNAL_LEADER_SKILL_DAM_TYPES


def skill_source_index(skill: Dict[str, Any], fallback: int) -> int:
    try:
        return int(skill.get("source_index"))
    except (TypeError, ValueError):
        return fallback


def normalize_battle_skill_pool(
    pet: Dict[str, Any],
    skills: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not skills:
        return []
    equipped_ids = {
        skill.get("skill_id")
        for skill in pet.get("equipped_skills", [])
        if skill.get("skill_id") is not None
    }
    ordered = sorted(
        [copy.deepcopy(skill) for skill in skills if isinstance(skill, dict) and skill.get("skill_id") is not None],
        key=lambda item: skill_source_index(item, len(skills)),
    )
    if not ordered:
        return []
    start_index = 0
    if equipped_ids:
        for idx, skill in enumerate(ordered):
            if skill.get("skill_id") in equipped_ids:
                start_index = idx
                break
    normalized: List[Dict[str, Any]] = []
    seen: set = set()
    for skill in ordered[start_index:]:
        skill_id = skill.get("skill_id")
        if skill_id in seen or is_internal_leader_skill(skill):
            continue
        seen.add(skill_id)
        item = copy.deepcopy(skill)
        item["pool_index"] = len(normalized)
        normalized.append(item)
    if equipped_ids and not equipped_ids.issubset({item.get("skill_id") for item in normalized}):
        return []
    return normalized


def apply_battle_skill_pool(
    pet: Optional[Dict[str, Any]],
    skills: List[Dict[str, Any]],
    *,
    source: str,
) -> None:
    if pet is None:
        return
    normalized = normalize_battle_skill_pool(pet, skills)
    if not normalized:
        return
    pet["skill_round_data"] = copy.deepcopy(skills)
    pet["battle_skill_pool"] = copy.deepcopy(normalized)
    pet["battle_skill_pool_source"] = source
    pet["skills"] = copy.deepcopy(normalized)
    if len(normalized) > len(pet.get("equipped_skills") or []):
        pet["leader_skill_pool"] = copy.deepcopy(normalized)
        pet["leader_skill_pool_source"] = source
