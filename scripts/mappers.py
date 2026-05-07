"""数据映射：wiki 原始数据 → 项目规范格式。"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TYPE_CHART_PATH = _PROJECT_ROOT / "data" / "game" / "type_chart.json"


def load_type_map(chart_path: Optional[Path] = None) -> Dict[str, int]:
    """从 type_chart.json 加载 {类型名: ID} 映射。"""
    path = chart_path or _TYPE_CHART_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {t["name"]: t["id"] for t in raw["types"]}


def map_pet(
    wiki_pet: dict,
    type_map: Dict[str, int],
    detail: Optional[dict] = None,
) -> Optional[dict]:
    """将 wiki 精灵数据转为规范格式。遇到未知类型返回 None。"""
    main_type_name = wiki_pet.get("主属性", "")
    sub_type_name = wiki_pet.get("2属性", "")

    types = []
    type_names = []
    warnings = []

    for tname in [main_type_name, sub_type_name]:
        if not tname:
            continue
        tid = type_map.get(tname)
        if tid is None:
            warnings.append(tname)
            continue
        types.append(tid)
        type_names.append(tname)

    if warnings:
        log.warning("跳过精灵 %s: 未知属性 %s", wiki_pet.get("wiki_name", "?"), warnings)
        return None

    stats = {
        "HP": _int_or_zero(wiki_pet.get("生命", "0")),
        "ATK": _int_or_zero(wiki_pet.get("物攻", "0")),
        "SPA": _int_or_zero(wiki_pet.get("魔攻", "0")),
        "DEF": _int_or_zero(wiki_pet.get("物防", "0")),
        "SPD": _int_or_zero(wiki_pet.get("魔防", "0")),
        "SPE": _int_or_zero(wiki_pet.get("速度", "0")),
    }

    result = {
        "wiki_name": wiki_pet.get("wiki_name", ""),
        "name": wiki_pet.get("精灵名称", wiki_pet.get("wiki_name", "")),
        "seq_id": wiki_pet.get("精灵序号", ""),
        "types": types,
        "type_names": type_names,
        "stats": stats,
        "stage": wiki_pet.get("精灵阶段", ""),
        "ability": wiki_pet.get("特性", ""),
    }

    if detail:
        result.update({
            "ability_desc": detail.get("特性描述", ""),
            "skills": _csv(detail.get("技能", "")),
            "skill_levels": _csv_int(detail.get("技能解锁等级", "")),
            "bloodline_skills": _csv(detail.get("血脉技能", "")),
            "learnable_stones": _csv(detail.get("可学技能石", "")),
            "evolution": detail.get("进化条件", ""),
            "version": detail.get("更新版本", ""),
        })

    return result


def map_skill(
    wiki_skill: dict,
    type_map: Dict[str, int],
) -> Optional[dict]:
    """将 wiki 技能数据转为规范格式。"""
    type_name = wiki_skill.get("属性", "")
    tid = type_map.get(type_name)

    result = {
        "wiki_name": wiki_skill.get("wiki_name", ""),
        "name": wiki_skill.get("技能名称", wiki_skill.get("wiki_name", "")),
        "type_name": type_name,
        "type_id": tid,
        "power": _int_or_zero(wiki_skill.get("威力", "0")),
        "skill_type": wiki_skill.get("技能类型", ""),
        "pp": _int_or_zero(wiki_skill.get("PP", "0")),
        "desc": wiki_skill.get("技能描述", ""),
    }
    return result


def map_pets(
    wiki_pets: List[dict],
    type_map: Dict[str, int],
    details: Optional[Dict[str, dict]] = None,
) -> Tuple[List[dict], List[str]]:
    """批量映射精灵，返回 (成功列表, 跳过的 wiki_name 列表)。"""
    details = details or {}
    mapped = []
    skipped = []
    for wp in wiki_pets:
        detail = details.get(wp.get("wiki_name", ""))
        pet = map_pet(wp, type_map, detail)
        if pet is None:
            skipped.append(wp.get("wiki_name", "?"))
        else:
            mapped.append(pet)
    return mapped, skipped


def map_skills(
    wiki_skills: List[dict],
    type_map: Dict[str, int],
) -> List[dict]:
    """批量映射技能。"""
    return [map_skill(ws, type_map) for ws in wiki_skills]


def _int_or_zero(val: str) -> int:
    if not val or val in ("-", "—", ""):
        return 0
    try:
        return int(val)
    except ValueError:
        try:
            return int(float(val))
        except ValueError:
            return 0


def _csv(val: str) -> List[str]:
    if not val or val == "-":
        return []
    return [s.strip() for s in val.split(",") if s.strip()]


def _csv_int(val: str) -> List[int]:
    return [_int_or_zero(s) for s in _csv(val)]
