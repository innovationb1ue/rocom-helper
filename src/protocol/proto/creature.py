"""宠物、技能、属性和初始 buff 的 protobuf 提取器。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.data.loader import (
    enrich_buff_modifiers,
    get_pet_meta,
    get_pet_skill_meta,
    get_pet_species_types,
    get_skill_meta,
)
from src.protocol.proto.constants import SDT_TO_TYPE, STAT_NAMES
from src.protocol.proto.lookups import buff_name, skill_name
from src.protocol.proto.tree import collect_varints, field_groups, first_text, pick_first
from src.protocol.proto.wire import maybe_signed64

logger = logging.getLogger(__name__)


def _attach_skill_meta(out: Dict[str, Any], skill_id: Optional[int]) -> None:
    if skill_id is None:
        return
    name = skill_name(skill_id)
    if name and not out.get("skill_name"):
        out["skill_name"] = name
    meta = get_skill_meta(skill_id)
    if not meta:
        return
    for src, dst in (
        ("desc", "skill_desc"), ("energy_cost", "skill_energy_cost"),
        ("target_type", "skill_target_type"), ("target_count", "skill_target_count"),
        ("skill_priority", "skill_priority"), ("damage_type", "skill_damage_type"),
        ("skill_feature", "skill_feature"), ("cd_round", "skill_cd_round"),
        ("skill_dam_type", "skill_dam_type"),
    ):
        if src in meta and dst not in out:
            out[dst] = meta[src]
    dam_type = meta.get("skill_dam_type")
    if dam_type is not None and "skill_element" not in out:
        out["skill_element"] = SDT_TO_TYPE.get(dam_type)


def extract_skills(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    skills, seen = [], set()
    for entry in field_groups(msg).get(12, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        for child in sub["fields"]:
            cs = child.get("sub")
            if cs is None:
                continue
            sid = pick_first(collect_varints(cs, 1), low=1_000_000)
            if sid is None:
                continue
            slot = pick_first(collect_varints(cs, 5), low=0, high=8) or 0
            pp = pick_first(collect_varints(cs, 8), low=0, high=99)
            key = (sid, slot, pp)
            if key in seen:
                continue
            seen.add(key)
            item = {"skill_id": sid, "equipped_slot": slot, "pp": pp}
            _attach_skill_meta(item, sid)
            skills.append(item)
    skills.sort(key=lambda it: (it["equipped_slot"] == 0, it["equipped_slot"], it["skill_id"]))
    return skills


def extract_skills_from_round_data(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 BattleInsidePetInfo.field 8 (PetSkillRoundData) 提取技能。"""
    skills, seen = [], set()
    for source_index, entry in enumerate(field_groups(msg).get(8, [])):
        sub = entry.get("sub")
        if sub is None:
            continue
        sid = pick_first(collect_varints(sub, 39))
        pos = pick_first(collect_varints(sub, 25))
        if sid is None or pos is None:
            continue
        key = (sid, pos)
        if key in seen:
            continue
        seen.add(key)
        cost_e = pick_first(collect_varints(sub, 9))
        item = {
            "skill_id": sid,
            "equipped_slot": pos,
            "pp": None,
            "cost_energy": cost_e,
            "source_index": source_index,
            "source": "battle_inside.skill_round_data",
        }
        _attach_skill_meta(item, sid)
        skills.append(item)
    skills.sort(key=lambda it: (it["equipped_slot"] == 0, it["equipped_slot"], it["skill_id"]))
    return skills


def extract_battle_buffs(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 BattleInsidePetInfo.field 5 (BattleBuffInfo) 提取初始 buff 列表。"""
    buffs: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for entry in field_groups(msg).get(5, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        buff_id = pick_first(collect_varints(sub, 2))
        if buff_id is None:
            continue
        if buff_id in seen_ids:
            continue
        seen_ids.add(buff_id)
        stack = pick_first(collect_varints(sub, 4))
        item = enrich_buff_modifiers({"id": buff_id, "name": buff_name(buff_id) or str(buff_id), "stage": stack})
        buffs.append(item)
    return buffs


def extract_simple_items(msg: Dict[str, Any], field_no: int, spec: Dict[int, Tuple[str, bool]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(field_no, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item: Dict[str, Any] = {}
        for fn, (name, signed) in spec.items():
            value = pick_first(collect_varints(sub, fn))
            if value is not None:
                item[name] = maybe_signed64(value) if signed else value
        if item:
            items.append(item)
    return items


def extract_stats(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    best: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(14, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        stats = []
        for idx in range(1, 7):
            sf = field_groups(sub).get(idx, [])
            if not sf:
                continue
            ss = sf[0].get("sub")
            if ss is None:
                continue
            base = pick_first(collect_varints(ss, 1), low=0, high=9999)
            calc = pick_first(collect_varints(ss, 3), low=0, high=99999)
            bonus = pick_first(collect_varints(ss, 6), low=0, high=99999)
            total = (calc + bonus) if calc is not None and bonus is not None else calc
            stats.append({"index": idx, "name": STAT_NAMES[idx - 1], "base": base, "calc": calc, "bonus": bonus, "total": total})
        if len(stats) > len(best):
            best = stats
    return best


def extract_creature(msg: Dict[str, Any], *, path: str, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = first_text(msg, 3)
    level = pick_first(collect_varints(msg, 10), low=1, high=100)
    if not name or level is None:
        return None
    slot = pick_first(collect_varints(msg, 1), low=0, high=999)
    pid = pick_first(collect_varints(msg, 2), low=1000)
    base_conf_id = pick_first(collect_varints(msg, 15))
    stats = extract_stats(msg)
    all_skills = extract_skills(msg)
    equipped = [it for it in all_skills if 1 <= it["equipped_slot"] <= 4]
    out: Dict[str, Any] = {
        "name": name, "level": level, "slot": slot, "pet_id": pid,
        "base_conf_id": base_conf_id,
        "types": [SDT_TO_TYPE.get(v, v) for v in collect_varints(msg, 6)],
        "stats": stats, "max_hp": stats[0]["total"] if stats else None,
        "skills": all_skills,
        "equipped_skills": sorted(equipped, key=lambda it: (it["equipped_slot"], it["skill_id"])),
        "source_opcode": record["opcode"], "source_opcode_hex": record.get("opcode_hex", ""),
        "seq": record.get("seq"), "path": path,
    }
    pet_meta_data = get_pet_meta(pid)
    if isinstance(pet_meta_data, dict):
        if pet_meta_data.get("base_id") is not None:
            out["base_id"] = pet_meta_data["base_id"]
        if pet_meta_data.get("pet_info_id") is not None:
            out["pet_info_id"] = pet_meta_data["pet_info_id"]
    if out.get("base_id") is not None:
        skill_pool = get_pet_skill_meta(out["base_id"])
        if isinstance(skill_pool, dict):
            out["base_skill_pool"] = skill_pool.get("level_skills") or []
    base_id = out.get("base_id")
    if base_id:
        species_types = get_pet_species_types(base_id)
        if species_types and species_types != out["types"]:
            logger.debug(
                "Type mismatch for %s (base_id=%s): protocol=%s, species=%s",
                name, base_id, out["types"], species_types,
            )
    return out

