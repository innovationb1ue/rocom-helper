"""宠物特性提取。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.data.loader import get_innate_skill, get_pet_innate_trait


def extract_traits(pet: Dict[str, Any]) -> List[Dict[str, str]]:
    traits: List[Dict[str, str]] = []
    seen_names: set = set()

    def _add(name: str, description: str) -> None:
        if name and name not in seen_names:
            seen_names.add(name)
            traits.append({"name": name, "description": description})

    wiki_trait = get_pet_innate_trait(pet.get("name", ""))
    if wiki_trait:
        _add(wiki_trait["name"], wiki_trait.get("description", ""))

    innate_id = pet.get("innate_skill_id")
    if innate_id:
        innate = get_innate_skill(innate_id)
        if innate is not None:
            _add(innate.get("name", "?"), innate.get("description", ""))

    for buff in pet.get("buffs", []):
        buff_id = buff.get("id")
        if buff_id is None:
            continue
        innate = get_innate_skill(buff_id)
        if innate is not None:
            _add(innate.get("name", "?"), innate.get("description", ""))

    return traits

