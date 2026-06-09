"""配置 API 的查询和响应组装。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.data.loader import (
    get_bundle,
    get_pet_meta,
    get_pet_skill_meta,
    get_skill_meta,
)


def resolve_popular_skill_name(base_id: int, requested_name: str = "") -> str:
    """解析热门技能预设显示名。"""
    if requested_name:
        return requested_name

    meta = get_pet_meta(base_id)
    if meta:
        return meta.get("name", str(base_id))

    skill_meta = get_pet_skill_meta(base_id)
    if skill_meta:
        return skill_meta.get("editor_name", str(base_id))

    return str(base_id)


def list_pets_with_learnable_skills() -> Dict[str, Any]:
    """获取有可学技能数据的精灵列表。"""
    pet_skill_meta = get_bundle().get("pet_skill_meta", {})
    results = []
    for base_id, entry in pet_skill_meta.items():
        level_skills = entry.get("level_skills")
        if not level_skills:
            continue
        results.append({
            "base_id": int(base_id),
            "name": entry.get("editor_name", ""),
            "skill_count": len(level_skills),
        })
    results.sort(key=lambda x: x["name"])
    return {"total": len(results), "pets": results}


def build_learnable_skill_payload(skill_id: int, level_skill: Dict[str, Any]) -> Dict[str, Any]:
    """构建单个可学技能响应。"""
    skill_meta = get_skill_meta(skill_id)
    return {
        "skill_id": skill_id,
        "name": skill_meta.get("name", "") if skill_meta else "",
        "element": skill_meta.get("element", 0) if skill_meta else 0,
        "damage_type": skill_meta.get("damage_type", 0) if skill_meta else 0,
        "energy_cost": skill_meta.get("energy_cost", 0) if skill_meta else 0,
        "power": skill_meta.get("power", 0) if skill_meta else 0,
        "desc": skill_meta.get("desc", "") if skill_meta else "",
        "source": level_skill.get("level_gain_skill", 1),
    }


def pet_learnable_skills_payload(base_id: int) -> Optional[Dict[str, Any]]:
    """获取某精灵全部可学技能响应；精灵不存在时返回 None。"""
    meta = get_pet_skill_meta(base_id)
    if meta is None:
        return None

    skills: List[Dict[str, Any]] = []
    for level_skill in meta.get("level_skills", []) or []:
        skill_id = level_skill.get("skill_id")
        if skill_id is None:
            continue
        skills.append(build_learnable_skill_payload(skill_id, level_skill))

    return {
        "base_id": base_id,
        "name": meta.get("editor_name", ""),
        "skills": skills,
    }
