"""折射技能池派生效果解析。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.constants import SDT_TO_TYPE
from src.data.loader import get_skill_meta, get_skill_name
from src.game.type_chart import TypeChart

REFLECT_SKILL_ID = 7060130
REFLECT_BUFF_ID = 20890020
REFLECT_BUFFBASE_ID = 2089001

_CHART = TypeChart()

REFLECT_EFFECTS_BY_ELEMENT: Dict[int, Dict[str, Any]] = {
    0: {"wrapper_buff_id": 20640140, "effect_buff_id": 20171870, "effect_name": "普通加威力", "kind": "power_up", "target_policy": "self"},
    3: {"wrapper_buff_id": 20640150, "effect_buff_id": 20171880, "effect_name": "草回血", "kind": "heal", "target_policy": "self"},
    1: {"wrapper_buff_id": 20640160, "effect_buff_id": 20171890, "effect_name": "火灼烧", "kind": "burn", "target_policy": "opponent"},
    2: {"wrapper_buff_id": 20640170, "effect_buff_id": 20171900, "effect_name": "水能耗降低", "kind": "energy_cost_down", "target_policy": "self"},
    17: {"wrapper_buff_id": 20640180, "effect_buff_id": 20171910, "effect_name": "光加魔攻", "kind": "spa_up", "target_policy": "self"},
    8: {"wrapper_buff_id": 20640190, "effect_buff_id": 20171930, "effect_name": "地降低速度和连击", "kind": "speed_combo_down", "target_policy": "opponent"},
    5: {"wrapper_buff_id": 20640200, "effect_buff_id": 20171940, "effect_name": "冰冻结", "kind": "freeze", "target_policy": "opponent"},
    15: {"wrapper_buff_id": 20640210, "effect_buff_id": 20171950, "effect_name": "龙降低魔防", "kind": "spd_down", "target_policy": "opponent"},
    4: {"wrapper_buff_id": 20640220, "effect_buff_id": 20171960, "effect_name": "电加速", "kind": "speed_up", "target_policy": "self"},
    7: {"wrapper_buff_id": 20640230, "effect_buff_id": 20171970, "effect_name": "毒中毒", "kind": "poison", "target_policy": "opponent"},
    12: {"wrapper_buff_id": 20640240, "effect_buff_id": 20171980, "effect_name": "虫降低物防", "kind": "def_down", "target_policy": "opponent"},
    6: {"wrapper_buff_id": 20640250, "effect_buff_id": 20171990, "effect_name": "武提高物攻", "kind": "atk_up", "target_policy": "self"},
    9: {"wrapper_buff_id": 20640260, "effect_buff_id": 20172000, "effect_name": "翼加连击", "kind": "hit_count_up", "target_policy": "self"},
    10: {"wrapper_buff_id": 20640270, "effect_buff_id": 20172010, "effect_name": "萌提高魔防", "kind": "spd_up", "target_policy": "self"},
    13: {"wrapper_buff_id": 20640280, "effect_buff_id": 20172020, "effect_name": "幽扣能量", "kind": "energy_down", "target_policy": "opponent"},
    16: {"wrapper_buff_id": 20640290, "effect_buff_id": 20172030, "effect_name": "恶获得吸血", "kind": "drain", "target_policy": "self"},
    14: {"wrapper_buff_id": 20640300, "effect_buff_id": 20172040, "effect_name": "机械提高防御", "kind": "def_up", "target_policy": "self"},
    11: {"wrapper_buff_id": 20640310, "effect_buff_id": 20172050, "effect_name": "幻星陨", "kind": "starfall", "target_policy": "opponent"},
}

REFLECT_EFFECT_BY_BUFF_ID: Dict[int, Dict[str, Any]] = {}
for _element, _effect in REFLECT_EFFECTS_BY_ELEMENT.items():
    for _key in ("wrapper_buff_id", "effect_buff_id"):
        REFLECT_EFFECT_BY_BUFF_ID[int(_effect[_key])] = {
            "element_id": _element,
            "element_name": _CHART.type_name(_element),
            **_effect,
        }


def reflect_skill_pool(pet: Dict[str, Any]) -> tuple[str, List[Dict[str, Any]]]:
    """按首领化技能优先级返回折射候选技能池。"""
    for key in ("leader_skill_pool", "battle_skill_pool", "skills", "equipped_skills", "base_skill_pool"):
        skills = [s for s in pet.get(key) or [] if isinstance(s, dict) and s.get("skill_id") is not None]
        if skills:
            return key, skills
    return "", []


def build_reflect_candidate_effects(pet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """根据宠物技能池属性生成折射候选效果；候选不代表真实已生效。"""
    pool_source, skills = reflect_skill_pool(pet)
    by_element: Dict[int, Dict[str, Any]] = {}
    for skill in skills:
        skill_id = skill.get("skill_id")
        element_id = _skill_element(skill)
        if element_id is None or element_id not in REFLECT_EFFECTS_BY_ELEMENT:
            continue
        effect = by_element.setdefault(
            element_id,
            {
                "element_id": element_id,
                "element_name": _CHART.type_name(element_id),
                "pool_source": pool_source,
                **REFLECT_EFFECTS_BY_ELEMENT[element_id],
                "source_skills": [],
            },
        )
        effect["source_skills"].append({
            "skill_id": skill_id,
            "skill_name": skill.get("skill_name") or get_skill_name(skill_id),
        })
    return [by_element[k] for k in sorted(by_element)]


def reflect_effect_for_buff(buff_id: Any, effect_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        parsed = int(buff_id)
    except (TypeError, ValueError):
        parsed = None
    if parsed is not None and parsed in REFLECT_EFFECT_BY_BUFF_ID:
        return dict(REFLECT_EFFECT_BY_BUFF_ID[parsed])
    if effect_name:
        for element, effect in REFLECT_EFFECTS_BY_ELEMENT.items():
            if effect["effect_name"] == effect_name:
                return {"element_id": element, "element_name": _CHART.type_name(element), **effect}
    return None


def _skill_element(skill: Dict[str, Any]) -> Optional[int]:
    if skill.get("skill_element") is not None:
        try:
            element = int(skill["skill_element"])
        except (TypeError, ValueError):
            element = None
        if element in REFLECT_EFFECTS_BY_ELEMENT:
            return element
    meta = get_skill_meta(skill.get("skill_id"))
    if not meta:
        return None
    raw = meta.get("skill_dam_type")
    element = SDT_TO_TYPE.get(raw, raw)
    return int(element) if element in REFLECT_EFFECTS_BY_ELEMENT else None
