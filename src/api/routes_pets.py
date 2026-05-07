"""精灵/技能/属性 API 路由。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from src.data.loader import (
    get_bundle, get_pet_meta, get_pet_name, get_skill_meta, get_skill_name,
    get_attr_meta, get_attr_name, get_buff_meta, get_pet_skill_meta,
)
from src.game.type_chart import TypeChart

router = APIRouter()

_chart = TypeChart()


@router.get("/pets")
async def list_pets(
    type_id: Optional[int] = Query(None, description="属性 ID 过滤"),
    name: Optional[str] = Query(None, description="名称搜索"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    bundle = get_bundle()
    pet_meta = bundle.get("pet_meta", {})
    results = []
    for pid_str, pet in pet_meta.items():
        pid = int(pid_str) if isinstance(pid_str, str) else pid_str
        entry = {"id": pid, "name": pet.get("name", ""), "base_id": pet.get("base_id")}
        if name and name.lower() not in pet.get("name", "").lower():
            continue
        if type_id is not None:
            pet_types = pet.get("types", [])
            if type_id not in pet_types:
                continue
        results.append(entry)
    total = len(results)
    results = results[offset:offset + limit]
    return {"total": total, "pets": results}


@router.get("/pets/{pet_id}")
async def get_pet_detail(pet_id: int):
    meta = get_pet_meta(pet_id)
    if meta is None:
        return {"error": "Pet not found"}
    skills = get_pet_skill_meta(meta.get("base_id", 0))
    return {"pet": meta, "skills": skills}


@router.get("/skills")
async def list_skills(
    type_id: Optional[int] = Query(None, description="属性 ID 过滤"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    bundle = get_bundle()
    skill_meta = bundle.get("skill_meta", {})
    results = []
    for sid_str, skill in skill_meta.items():
        entry = {
            "id": int(sid_str) if isinstance(sid_str, str) else sid_str,
            "name": skill.get("name", ""),
            "type": skill.get("type"),
            "power": skill.get("dam_para", [0])[0] if skill.get("dam_para") else 0,
            "energy_cost": skill.get("energy_cost", [0])[0] if skill.get("energy_cost") else 0,
            "hit_rate": skill.get("hit_para", 0),
        }
        if type_id is not None and entry["type"] != type_id:
            continue
        results.append(entry)
    total = len(results)
    results = results[offset:offset + limit]
    return {"total": total, "skills": results}


@router.get("/skills/{skill_id}")
async def get_skill_detail(skill_id: int):
    meta = get_skill_meta(skill_id)
    if meta is None:
        return {"error": "Skill not found"}
    return meta


@router.get("/types")
async def list_types():
    return {"types": _chart.all_types()}


@router.get("/types/{type_id}/matchups")
async def get_type_matchups(type_id: int):
    if type_id not in {t["id"] for t in _chart.all_types()}:
        return {"error": "Type not found"}
    weaknesses = _chart.get_weaknesses([type_id])
    resistances = _chart.get_resistances([type_id])
    immunities = _chart.get_immunities([type_id])
    return {
        "type_id": type_id,
        "type_name": _chart.type_name(type_id),
        "weaknesses": {_chart.type_name(k): v for k, v in weaknesses.items()},
        "resistances": {_chart.type_name(k): v for k, v in resistances.items()},
        "immunities": [_chart.type_name(i) for i in immunities],
    }
