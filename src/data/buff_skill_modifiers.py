"""技能威力和连击类 buff 修正查询。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.data.buff_effects import iter_effective_buff_ids

_POWER_FLAT_BUFF_IDS = {
    20230440: 10,  # 通用威力+10
}
_HIT_FLAT_BUFF_IDS = {
    20450050: 1,   # 通用连击次数+1
    20450090: -1,  # 通用连击次数-1
}
_GENERIC_DAMAGE_MODIFIER_BUFF_IDS = set(_POWER_FLAT_BUFF_IDS) | set(_HIT_FLAT_BUFF_IDS)

# 折射派生的威力类效果按技能属性过滤；普通=0。
_POWER_ELEMENT_SCOPES = {
    20640140: 0,  # 普通
    20171870: 0,  # 普通加威力
}

# 翼加连击这类效果不是“只给翼系技能”，而是给已经具备连击形态的技能追加段数。
_MULTI_HIT_ONLY_ROOT_IDS = {
    20640260,  # 翼
    20172000,  # 翼加连击
}

_REFLECT_PARENT_BUFF_IDS = {20890020}
_REFLECT_PARENT_BUFFBASE_IDS = {2089001}

def _source_skill_applies(
    source_buff: Dict[str, Any],
    *,
    skill_name: Optional[str],
) -> bool:
    source_skill = source_buff.get("source_skill")
    return not (source_skill and skill_name and source_skill != skill_name)


def _power_modifier_applies(
    root_id: int,
    source_buff: Dict[str, Any],
    *,
    skill_element: Optional[int],
    skill_name: Optional[str],
) -> bool:
    if not _source_skill_applies(source_buff, skill_name=skill_name):
        return False
    source_skill = source_buff.get("source_skill")
    scoped_element = _POWER_ELEMENT_SCOPES.get(root_id)
    if scoped_element is not None and skill_element is not None:
        return scoped_element == skill_element
    if skill_element is not None and root_id in _GENERIC_DAMAGE_MODIFIER_BUFF_IDS and not source_skill:
        return False
    return True


def _hit_modifier_applies(
    root_id: int,
    source_buff: Dict[str, Any],
    *,
    skill_name: Optional[str],
    base_hit_count: Optional[int],
    allow_reflect_derived_hit: bool,
) -> bool:
    if not _source_skill_applies(source_buff, skill_name=skill_name):
        return False
    if (
        root_id in _MULTI_HIT_ONLY_ROOT_IDS
        and not allow_reflect_derived_hit
        and _is_reflect_derived_buff(source_buff)
    ):
        return False
    if root_id in _MULTI_HIT_ONLY_ROOT_IDS and base_hit_count is not None:
        return base_hit_count > 1
    if root_id in _GENERIC_DAMAGE_MODIFIER_BUFF_IDS and not source_buff.get("source_skill"):
        return False
    return True


def _is_reflect_derived_buff(source_buff: Dict[str, Any]) -> bool:
    return (
        source_buff.get("parent_buff_name") == "折射"
        or source_buff.get("parent_buff_id") in _REFLECT_PARENT_BUFF_IDS
        or source_buff.get("parent_buffbase_id") in _REFLECT_PARENT_BUFFBASE_IDS
    )


def get_buff_power_modifiers(
    buff_list: List[Dict[str, Any]],
    *,
    skill_element: Optional[int] = None,
    skill_name: Optional[str] = None,
) -> Dict[str, float]:
    """解析 buff 派生的技能威力修正。当前返回 flat 加值。"""
    flat = 0.0
    sources: List[int] = []
    for buff_id, root_id, source_buff in iter_effective_buff_ids(buff_list):
        if not _power_modifier_applies(
            root_id,
            source_buff,
            skill_element=skill_element,
            skill_name=skill_name,
        ):
            continue
        value = _POWER_FLAT_BUFF_IDS.get(buff_id)
        if value is None:
            continue
        flat += value
        sources.append(buff_id)
    return {"flat": flat, "sources": sources} if flat else {}


def get_buff_hit_count_modifiers(
    buff_list: List[Dict[str, Any]],
    *,
    skill_element: Optional[int] = None,
    skill_name: Optional[str] = None,
    base_hit_count: Optional[int] = None,
    allow_reflect_derived_hit: bool = True,
) -> Dict[str, float]:
    """解析 buff 派生的连击次数修正。当前返回 flat 加值。"""
    flat = 0.0
    sources: List[int] = []
    for buff_id, root_id, source_buff in iter_effective_buff_ids(buff_list):
        if not _hit_modifier_applies(
            root_id,
            source_buff,
            skill_name=skill_name,
            base_hit_count=base_hit_count,
            allow_reflect_derived_hit=allow_reflect_derived_hit,
        ):
            continue
        value = _HIT_FLAT_BUFF_IDS.get(buff_id)
        if value is None:
            continue
        flat += value
        sources.append(buff_id)
    return {"flat": flat, "sources": sources} if flat else {}
