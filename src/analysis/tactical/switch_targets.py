"""战术换宠目标推断。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.counter import CounterPicker
from src.analysis.models import OpponentAction
from src.analysis.pet_identity import same_battle_pet
from src.game.type_chart import TypeChart


def normalize_pet_for_analysis(pet: Dict[str, Any]) -> Dict[str, Any]:
    """将战斗状态宠物转换为 ThreatAssessor / CounterPicker 期望的格式。"""
    normalized = dict(pet)

    stats = pet.get("stats", [])
    if isinstance(stats, list):
        stats_dict: Dict[str, Any] = {}
        for stat in stats:
            name = stat.get("name")
            value = stat.get("total") or stat.get("calc") or 0
            if name:
                stats_dict[name] = value
        normalized["stats"] = stats_dict
    elif isinstance(stats, dict):
        normalized["stats"] = stats

    if "base_speed" in pet and "SPE" not in normalized.get("stats", {}):
        normalized.setdefault("stats", {})["SPE"] = pet["base_speed"]

    skills = pet.get("equipped_skills") or pet.get("skills") or []
    normalized_skills: List[Dict[str, Any]] = []
    for skill in skills:
        normalized_skill = dict(skill)
        if "skill_element" in skill and "type_id" not in skill:
            normalized_skill["type_id"] = skill["skill_element"]
        if "skill_name" in skill and "name" not in skill:
            normalized_skill["name"] = skill["skill_name"]
        normalized_skills.append(normalized_skill)
    normalized["skills"] = normalized_skills

    return normalized


class SwitchTargetResolver:
    """根据声明目标或属性反制关系推断对手换宠目标。"""

    def __init__(self, chart: TypeChart) -> None:
        self._counter = CounterPicker(chart)

    def most_likely_switch_target(
        self,
        opp_action: OpponentAction,
        opp_pets: List[Dict[str, Any]],
        my_active: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """猜测对手最可能换上的宠物（按名称匹配或按反制优势）。"""
        target_name = opp_action.switch_to_name
        for pet in opp_pets:
            if pet.get("name") == target_name and pet.get("current_hp", 1) > 0:
                return pet

        living_bench = [
            pet for pet in opp_pets
            if pet.get("current_hp", 1) > 0
        ]
        if not living_bench:
            return None

        norm_my_active = normalize_pet_for_analysis(my_active)
        norm_bench = [normalize_pet_for_analysis(pet) for pet in living_bench]
        counters = self._counter.find_counters([norm_my_active], norm_bench, top_n=1)
        if counters:
            counter = counters[0]
            for pet in living_bench:
                if same_battle_pet(pet, counter):
                    return pet

        return living_bench[0]
