"""宠物技能池数据查询。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.data.catalog import _get_bundle_meta
from src.data.pet_species import get_pet_species


def get_pet_skill_meta(base_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """按 base_id 查找宠物技能数据。

    leader/boss 形态有独立的 base_id 但共享基础形态的 level_skill_conf_id，
    此函数会自动 fallback。
    """
    if base_id is None:
        return None
    result = _get_bundle_meta("pet_skill_meta", value=base_id)
    if result is not None:
        return result
    sp = get_pet_species(base_id)
    if sp:
        level_skill_conf_id = sp.get("level_skill_conf_id")
        if level_skill_conf_id:
            return _get_bundle_meta("pet_skill_meta", value=level_skill_conf_id)
    return None
