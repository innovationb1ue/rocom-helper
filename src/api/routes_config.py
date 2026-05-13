"""热门技能预设配置 API 路由。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.data.loader import (
    get_all_popular_skills,
    get_popular_skills,
    save_popular_skills,
    delete_popular_skills,
    get_pet_skill_meta,
    get_pet_meta,
    get_skill_meta,
)

router = APIRouter()


class PopularSkillUpdate(BaseModel):
    """更新热门技能预设的请求体。"""
    name: str = ""
    skills: List[int] = []
    note: str = ""


@router.get("/config/popular-skills")
async def list_popular_skills():
    """获取全部热门技能预设。"""
    return get_all_popular_skills()


@router.get("/config/popular-skills/{base_id}")
async def get_popular_skill(base_id: int):
    """获取某精灵的热门技能预设。"""
    preset = get_popular_skills(base_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="No preset found for this pet")
    return {"base_id": base_id, **preset}


@router.put("/config/popular-skills/{base_id}")
async def update_popular_skill(base_id: int, body: PopularSkillUpdate):
    """更新某精灵的热门技能预设。"""
    name = body.name
    if not name:
        meta = get_pet_meta(base_id)
        if meta:
            name = meta.get("name", str(base_id))
        else:
            # 尝试从 pet_skill_meta 获取名称
            skill_meta = get_pet_skill_meta(base_id)
            if skill_meta:
                name = skill_meta.get("editor_name", str(base_id))
            else:
                name = str(base_id)
    save_popular_skills(base_id, name, body.skills, body.note)
    return {"ok": True, "base_id": base_id, "name": name, "skills": body.skills}


@router.delete("/config/popular-skills/{base_id}")
async def delete_popular_skill(base_id: int):
    """删除某精灵的热门技能预设。"""
    found = delete_popular_skills(base_id)
    if not found:
        raise HTTPException(status_code=404, detail="No preset found for this pet")
    return {"ok": True, "base_id": base_id}


@router.get("/config/pets-with-skills")
async def list_pets_with_skills():
    """获取有可学技能数据的精灵列表（用于配置页面选择精灵）。"""
    bundle_meta = get_pet_skill_meta
    # 从 pet_skill_meta 获取所有有技能的精灵
    from src.data.loader import get_bundle
    bundle = get_bundle()
    pet_skill_meta = bundle.get("pet_skill_meta", {})
    results = []
    for bid_str, entry in pet_skill_meta.items():
        ls = entry.get("level_skills")
        if not ls or len(ls) == 0:
            continue
        bid = int(bid_str)
        results.append({
            "base_id": bid,
            "name": entry.get("editor_name", ""),
            "skill_count": len(ls),
        })
    results.sort(key=lambda x: x["name"])
    return {"total": len(results), "pets": results}


@router.get("/config/pets-with-skills/{base_id}/skills")
async def list_pet_learnable_skills(base_id: int):
    """获取某精灵的全部可学技能列表（用于配置页面选择技能）。"""
    meta = get_pet_skill_meta(base_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Pet not found in skill map")
    level_skills = meta.get("level_skills", [])
    if not level_skills:
        return {"base_id": base_id, "name": meta.get("editor_name", ""), "skills": []}
    skills = []
    for ls in level_skills:
        skill_id = ls.get("skill_id")
        if skill_id is None:
            continue
        skill_meta = get_skill_meta(skill_id)
        skills.append({
            "skill_id": skill_id,
            "name": skill_meta.get("name", "") if skill_meta else "",
            "element": skill_meta.get("element", 0) if skill_meta else 0,
            "damage_type": skill_meta.get("damage_type", 0) if skill_meta else 0,
            "energy_cost": skill_meta.get("energy_cost", 0) if skill_meta else 0,
            "power": skill_meta.get("power", 0) if skill_meta else 0,
            "desc": skill_meta.get("desc", "") if skill_meta else "",
            "source": ls.get("level_gain_skill", 1),
        })
    return {"base_id": base_id, "name": meta.get("editor_name", ""), "skills": skills}
