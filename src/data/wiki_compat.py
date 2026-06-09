"""旧 wiki 数据查询兼容层。

这些入口保留历史函数名，实际数据已经来自 BinData 导出的 JSON。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.data.catalog import get_bundle
from src.data.pet_species import get_species_by_name


def get_wiki_pet(name: str) -> Optional[Dict[str, Any]]:
    """按名称查找精灵物种数据（来自 pet_species.json）。"""
    return get_species_by_name(name)


def get_wiki_skill(name: str) -> Optional[Dict[str, Any]]:
    """按名称查找技能数据（来自 skill_map.json）。已弃用，仅保留向后兼容。"""
    skill_meta = get_bundle().get("skill_meta", {})
    for entry in skill_meta.values():
        if entry.get("name") == name:
            return entry
    return None


def get_wiki_pet_types(name: str) -> List[int]:
    """获取精灵的属性 ID 列表（来自 pet_species.json）。"""
    sp = get_species_by_name(name)
    if sp and sp.get("types"):
        return sp["types"]
    return []


def get_wiki_pet_stats(name: str) -> Dict[str, int]:
    """获取精灵种族值（来自 pet_species.json，key 为小写 hp/atk/spa/def/spd/spe）。"""
    sp = get_species_by_name(name)
    if sp and sp.get("stats"):
        return sp["stats"]
    return {}
