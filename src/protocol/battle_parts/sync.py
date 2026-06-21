"""Sync-data extraction helpers for battle perform entries."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.protocol.battle_parts.sync_common import _pick_sync_value
from src.protocol.battle_parts.sync_items import (
    _COMM_SYNC_FIELDS,
    _ITEM_SYNC_FIELDS,
    _PET_SYNC_FIELDS,
    _ROLE_SYNC_FIELDS,
    _SKILL_SYNC_FIELDS,
    _extract_sync_items,
    _extract_task_infos,
)
from src.protocol.battle_parts.sync_skill import _extract_pet_skill_round_data
from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    first_sub,
    normalize_skill_id,
    pick_first,
    skill_name,
    extract_creature,
)
from src.protocol.battle_schema import _compact_dict


def _extract_skill_change_sync(sync: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(sync).get(5, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        sid = normalize_skill_id(_pick_sync_value(sub, 2, False))
        skill_data = {}
        skill_sub = first_sub(field_groups(sub).get(3, []))
        if skill_sub:
            skill_data = _extract_pet_skill_round_data(skill_sub)
        item = _compact_dict({
            "pet_id": _pick_sync_value(sub, 1, False),
            "skill_id": sid or skill_data.get("skill_id"),
            "skill_name": skill_name(sid or skill_data.get("skill_id")),
            "skill_data": skill_data,
        })
        if item:
            items.append(item)
    return items


def _extract_pet_info_sync(sync: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(sync).get(6, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        common = first_sub(field_groups(sub).get(2, []))
        creature = extract_creature(
            common,
            path="sync_data.pet_info",
            record={"opcode": 0x1324, "opcode_hex": "0x1324"},
        ) if common else None
        compact_skills = []
        for skill in (creature or {}).get("equipped_skills", []):
            compact_skills.append(_compact_dict({
                "skill_id": skill.get("skill_id"),
                "skill_name": skill.get("skill_name"),
                "equipped_slot": skill.get("equipped_slot"),
                "cost_energy": skill.get("cost_energy"),
            }))
        skill_round_data = []
        for skill in (creature or {}).get("skills", []):
            skill_round_data.append(_compact_dict({
                "skill_id": skill.get("skill_id"),
                "skill_name": skill.get("skill_name"),
                "skill_element": skill.get("skill_element"),
                "damage_type": skill.get("damage_type") or skill.get("skill_damage_type"),
                "skill_dam_type": skill.get("skill_dam_type"),
                "equipped_slot": skill.get("equipped_slot"),
                "cost_energy": skill.get("cost_energy"),
                "source_index": skill.get("source_index"),
                "source": skill.get("source") or "sync_data.pet_info.skill_round_data",
            }))
        item = _compact_dict({
            "pet_id": (creature or {}).get("pet_id"),
            "name": (creature or {}).get("name"),
            "level": (creature or {}).get("level"),
            "base_conf_id": (creature or {}).get("base_conf_id"),
            "types": (creature or {}).get("types"),
            "max_hp": (creature or {}).get("max_hp"),
            "equipped_skills": compact_skills,
            "skill_round_data": skill_round_data,
            "data_level": _pick_sync_value(sub, 4, True),
            "full_for_data_level": bool(_pick_sync_value(sub, 5, False) or 0),
        })
        if item:
            items.append(item)
    return items


def _extract_pet_skill_updates(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """解析 BattleDataUpdate.pet_skill，补全战斗中的技能运行时数据。"""
    updates: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(7, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        update: Dict[str, Any] = {
            "pet_id": pick_first(collect_varints(sub, 1)),
            "skills": [],
        }
        for source_index, skill_entry in enumerate(field_groups(sub).get(2, [])):
            skill_sub = skill_entry.get("sub")
            if skill_sub is None:
                continue
            skill = _extract_pet_skill_round_data(skill_sub)
            if skill:
                skill.setdefault("source_index", source_index)
                skill.setdefault("source", "data_update.pet_skill.skills")
                update["skills"].append(skill)
        update = _compact_dict(update)
        if update:
            updates.append(update)
    return updates


def _extract_sync_data(sync: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if sync is None:
        return {}
    return _compact_dict({
        "role_sync": _extract_sync_items(sync, 1, _ROLE_SYNC_FIELDS),
        "pet_sync": _extract_sync_items(sync, 2, _PET_SYNC_FIELDS),
        "skill_sync": _extract_sync_items(sync, 3, _SKILL_SYNC_FIELDS),
        "comm_sync": _extract_sync_items(sync, 4, _COMM_SYNC_FIELDS),
        "skill_change_sync": _extract_skill_change_sync(sync),
        "pet_info": _extract_pet_info_sync(sync),
        "item_sync": _extract_sync_items(sync, 7, _ITEM_SYNC_FIELDS),
        "task_infos": _extract_task_infos(sync),
    })



def compact_optional(data: Dict[str, Any]) -> Dict[str, Any]:
    """Drop None values while preserving falsey protocol values such as 0."""
    return {key: value for key, value in data.items() if value is not None}
