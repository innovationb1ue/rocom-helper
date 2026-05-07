"""队伍分析/反制推荐 API 路由。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body

from src.data.loader import get_pet_meta, get_skill_meta, get_bundle, get_wiki_pet, get_wiki_skill
from src.game.type_chart import TypeChart
from src.analysis.team_builder import TeamBuilder
from src.analysis.counter import CounterPicker
from src.analysis.coverage import CoverageAnalyzer

router = APIRouter()

_chart = TypeChart()
_builder = TeamBuilder(_chart)
_counter = CounterPicker(_chart)
_coverage = CoverageAnalyzer(_chart)


def _build_pet_info(pet_id: int) -> Dict[str, Any]:
    meta = get_pet_meta(pet_id)
    if meta is None:
        return {"id": pet_id, "name": f"Unknown({pet_id})", "types": [], "skills": [], "stats": {}}
    name = meta.get("name", "")
    wiki = get_wiki_pet(name)

    # 属性：优先 wiki
    types = wiki.get("types", []) if wiki else []
    if not types:
        types = meta.get("types", [])

    # 种族值：优先 wiki
    stats = wiki.get("stats", {}) if wiki else {}
    if not stats:
        stats = meta.get("stats", {})

    # 技能：wiki 技能名 → 查 wiki_skills.json 获取 type_id
    skills = []
    if wiki and wiki.get("skills"):
        for sk_name in wiki["skills"]:
            ws = get_wiki_skill(sk_name)
            skills.append({
                "id": 0,
                "name": sk_name,
                "type_id": ws.get("type_id") if ws else None,
                "power": ws.get("power", 0) if ws else 0,
                "energy_cost": 0,
            })
    else:
        bundle = get_bundle()
        psk = bundle.get("pet_skill_meta", {}).get(str(meta.get("base_id", "")))
        if psk:
            for sk in psk.get("skills", []):
                sk_id = sk.get("skill_id") or sk.get("id")
                if sk_id:
                    sm = get_skill_meta(sk_id)
                    if sm:
                        skills.append({
                            "id": sk_id,
                            "name": sm.get("name", ""),
                            "type_id": sm.get("type"),
                            "power": sm.get("dam_para", [0])[0] if sm.get("dam_para") else 0,
                            "energy_cost": sm.get("energy_cost", [0])[0] if sm.get("energy_cost") else 0,
                        })

    return {
        "id": pet_id,
        "name": name,
        "types": types,
        "base_id": meta.get("base_id"),
        "skills": skills,
        "stats": stats,
    }


@router.post("/analyze")
async def analyze_team(pet_ids: List[int] = Body(..., embed=True)):
    pets = [_build_pet_info(pid) for pid in pet_ids]
    result = _builder.analyze_team(pets)
    return result


@router.post("/counter")
async def find_counters(
    opponent_ids: List[int] = Body(..., embed=True),
    pool_ids: Optional[List[int]] = Body(None, embed=True),
):
    opponents = [_build_pet_info(pid) for pid in opponent_ids]
    if pool_ids:
        pool = [_build_pet_info(pid) for pid in pool_ids]
    else:
        # Use all pets as pool
        bundle = get_bundle()
        pool = []
        for pid_str in list(bundle.get("pet_meta", {}).keys())[:200]:
            pool.append(_build_pet_info(int(pid_str)))
    counters = _counter.find_counters(opponents, pool, top_n=10)
    return {"counters": counters}


@router.post("/suggest")
async def suggest_teammates(
    core_ids: List[int] = Body(..., embed=True),
    pool_ids: Optional[List[int]] = Body(None, embed=True),
    top_n: int = Body(5, embed=True),
):
    core = [_build_pet_info(pid) for pid in core_ids]
    if pool_ids:
        pool = [_build_pet_info(pid) for pid in pool_ids]
    else:
        bundle = get_bundle()
        pool = []
        for pid_str in list(bundle.get("pet_meta", {}).keys())[:200]:
            pool.append(_build_pet_info(int(pid_str)))
    suggestions = _builder.suggest_teammates(core, pool, top_n=top_n)
    return {"suggestions": suggestions}


@router.post("/coverage")
async def coverage_report(pet_ids: List[int] = Body(..., embed=True)):
    pets = [_build_pet_info(pid) for pid in pet_ids]
    off = _coverage.offensive_coverage(pets)
    def_cov = _coverage.defensive_coverage(pets)
    score = _coverage.coverage_score(pets)
    uncovered = _coverage.uncovered_types(pets)
    shared = _coverage.shared_weaknesses(pets)
    return {
        "score": round(score, 1),
        "offensive_coverage": off,
        "defensive_coverage": def_cov,
        "uncovered_types": uncovered,
        "shared_weaknesses": shared,
    }
