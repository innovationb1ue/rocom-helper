"""热门技能预设配置 API 路由。"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from src.api.config_route_actions import (
    delete_popular_skill_payload,
    get_popular_skill_payload,
    list_popular_skills_payload,
    pet_learnable_skills_or_404,
    pets_with_learnable_skills_payload,
    update_popular_skill_payload,
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
    return list_popular_skills_payload()


@router.get("/config/popular-skills/{base_id}")
async def get_popular_skill(base_id: int):
    """获取某精灵的热门技能预设。"""
    return get_popular_skill_payload(base_id)


@router.put("/config/popular-skills/{base_id}")
async def update_popular_skill(base_id: int, body: PopularSkillUpdate):
    """更新某精灵的热门技能预设。"""
    return update_popular_skill_payload(base_id, name=body.name, skills=body.skills, note=body.note)


@router.delete("/config/popular-skills/{base_id}")
async def delete_popular_skill(base_id: int):
    """删除某精灵的热门技能预设。"""
    return delete_popular_skill_payload(base_id)


@router.get("/config/pets-with-skills")
async def list_pets_with_skills():
    """获取有可学技能数据的精灵列表（用于配置页面选择精灵）。"""
    return pets_with_learnable_skills_payload()


@router.get("/config/pets-with-skills/{base_id}/skills")
async def list_pet_learnable_skills(base_id: int):
    """获取某精灵的全部可学技能列表（用于配置页面选择技能）。"""
    return pet_learnable_skills_or_404(base_id)
