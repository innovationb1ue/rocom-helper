"""PetSkillRoundData and skill runtime sync extractors."""
from __future__ import annotations

from typing import Any, Dict, List

from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    first_sub,
    maybe_signed64,
    normalize_skill_id,
    skill_name,
    _attach_skill_meta,
)
from src.protocol.battle_parts.sync_common import (
    _extract_simple_subitems,
    _pick_fixed32_float,
    _pick_sync_value,
)
from src.protocol.battle_schema import _compact_dict


def _extract_damage_params(msg: Dict[str, Any], field_no: int) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(field_no, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            "pet_id": _pick_sync_value(sub, 1, False),
            "damage_param": _pick_sync_value(sub, 2, False),
        })
        if item:
            items.append(item)
    return items


def _extract_restraint_types(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(27, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            "pet_id": _pick_sync_value(sub, 1, False),
            "restraint_type": _pick_sync_value(sub, 2, True),
        })
        if item:
            items.append(item)
    return items


def _extract_extra_damage_types(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(32, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            "values": collect_varints(sub, 1),
            "source": _pick_sync_value(sub, 2, False),
        })
        if item:
            items.append(item)
    return items


def _extract_cr_damage_params(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _extract_simple_subitems(msg, 41, {
        1: ("pet_id", False),
        2: ("param", True),
    })


def _extract_skill_buff_info(msg: Dict[str, Any]) -> Dict[str, Any]:
    sub = first_sub(field_groups(msg).get(45, []))
    if sub is None:
        return {}
    return _compact_dict({
        "hp_per_energy": _pick_fixed32_float(sub, 1),
        "damage_param": _pick_sync_value(sub, 2, True),
        "damage_param_by": _pick_sync_value(sub, 3, True),
        "energy_cost": _pick_sync_value(sub, 4, True),
        "energy_cost_by": _pick_sync_value(sub, 5, True),
        "multiply": _pick_sync_value(sub, 6, True),
        "multiply_by": _pick_sync_value(sub, 7, True),
        "priority": _pick_sync_value(sub, 8, True),
        "cast_cnt": _pick_sync_value(sub, 9, True),
        "trans_time": _pick_sync_value(sub, 10, True),
    })


def _extract_trans_info(msg: Dict[str, Any]) -> Dict[str, Any]:
    sub = first_sub(field_groups(msg).get(48, []))
    if sub is None:
        return {}
    return _compact_dict({
        "trans_time": _pick_sync_value(sub, 1, True),
        "initial_pos": _pick_sync_value(sub, 2, False),
    })


def _extract_set_cost_info(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _extract_simple_subitems(msg, 59, {
        1: ("reason_id", False),
        2: ("cost", True),
    })


def _extract_cd_info(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(34, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            "buff_id": _pick_sync_value(sub, 1, False),
            "value": _pick_sync_value(sub, 2, True),
        })
        if item:
            items.append(item)
    return items


def _extract_enhance_info(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(35, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            "buff_id": _pick_sync_value(sub, 1, False),
            "effect_ids": [maybe_signed64(v) for v in collect_varints(sub, 2)],
            "cast_moment": _pick_sync_value(sub, 3, False),
            "tip_id": _pick_sync_value(sub, 4, False),
            "skill_id": normalize_skill_id(_pick_sync_value(sub, 5, False)),
            "stack": _pick_sync_value(sub, 6, False),
            "buffbase_id": _pick_sync_value(sub, 7, False),
            "skill_type": _pick_sync_value(sub, 8, True),
            "caster_pet_base_id": _pick_sync_value(sub, 10, False),
        })
        if item:
            items.append(item)
    return items


def _extract_pet_skill_round_data(msg: Dict[str, Any]) -> Dict[str, Any]:
    """解析 PetSkillRoundData。field 2 是状态，field 3 是类型，field 39 才是技能 ID。"""
    sid = normalize_skill_id(_pick_sync_value(msg, 39, False))
    item = _compact_dict({
        "raw_round_skill_id": _pick_sync_value(msg, 1, False),
        "skill_id": sid,
        "skill_name": skill_name(sid),
        "state": _pick_sync_value(msg, 2, True),
        "type": _pick_sync_value(msg, 3, False),
        "cast_cnt": _pick_sync_value(msg, 4, True),
        "cost_hp": _pick_sync_value(msg, 5, False),
        "display_hp": bool(_pick_sync_value(msg, 6, False) or 0),
        "hp_per_energy": _pick_fixed32_float(msg, 7),
        "last_cast_round": _pick_sync_value(msg, 8, True),
        "cost_energy": _pick_sync_value(msg, 9, False),
        "cost_energy_buff": _pick_sync_value(msg, 10, True),
        "cost_energy_buff_factor": _pick_sync_value(msg, 11, True),
        "cost_energy_buff_mul": _pick_sync_value(msg, 12, True),
        "cost_energy_buff_set": _pick_sync_value(msg, 13, True),
        "sp_energy_skill": _pick_sync_value(msg, 14, False),
        "carryon_slot_idx": _pick_sync_value(msg, 15, True),
        "consume_energy": _pick_sync_value(msg, 16, True),
        "consume_hp": _pick_sync_value(msg, 17, True),
        "ex_damage_param": _pick_sync_value(msg, 18, True),
        "cost_all_energy": bool(_pick_sync_value(msg, 19, False) or 0),
        "fever_state": bool(_pick_sync_value(msg, 20, False) or 0),
        "rule_energy": _pick_sync_value(msg, 21, True),
        "rule_damage_param": _pick_sync_value(msg, 22, True),
        "effect_damage_param": _pick_sync_value(msg, 23, True),
        "buff_damage_param": _pick_sync_value(msg, 24, True),
        "equipped_slot": _pick_sync_value(msg, 25, False),
        "cd_round": _pick_sync_value(msg, 28, True),
        "flag": _pick_sync_value(msg, 29, False),
        "raw_damage": _pick_sync_value(msg, 30, True),
        "used_cnt": _pick_sync_value(msg, 31, False),
        "disable_conf_dam_type": bool(_pick_sync_value(msg, 33, False) or 0),
        "change_times": _pick_sync_value(msg, 36, True),
        "cr_reset_round": _pick_sync_value(msg, 37, True),
        "cr_reset_reason": _pick_sync_value(msg, 38, True),
        "used_cnt_for_evolute": _pick_sync_value(msg, 40, False),
        "change_src_skill": normalize_skill_id(_pick_sync_value(msg, 42, False)),
        "state_tips": _pick_sync_value(msg, 43, False),
        "must_cost_hp": bool(_pick_sync_value(msg, 44, False) or 0),
        "last_pos": _pick_sync_value(msg, 47, False),
        "consume_change_effeciency": _pick_sync_value(msg, 49, False),
        "is_change_effeciency": _pick_sync_value(msg, 50, False),
        "original_pos": _pick_sync_value(msg, 51, False),
        "raw_cost_energy": _pick_sync_value(msg, 52, False),
        "cast_rounds": _pick_sync_value(msg, 53, False),
        "enable_on_charging": bool(_pick_sync_value(msg, 54, False) or 0),
        "round_start_pos": _pick_sync_value(msg, 55, False),
        "last_round_pos": _pick_sync_value(msg, 56, False),
        "swap_from_pet": _pick_sync_value(msg, 57, False),
        "priority_display": bool(_pick_sync_value(msg, 58, False) or 0),
        "perform_flag": _pick_sync_value(msg, 60, False),
        "remove_round": _pick_sync_value(msg, 61, True),
        "original_skill_id": normalize_skill_id(_pick_sync_value(msg, 62, False)),
        "damage_type": _pick_sync_value(msg, 63, True),
        "cost_energy_buff_mul_10000": _pick_sync_value(msg, 64, True),
        "cost_energy_buff_factor_list": [maybe_signed64(v) for v in collect_varints(msg, 65)],
        "cd_outfield_round": _pick_sync_value(msg, 66, True),
        "season_id": _pick_sync_value(msg, 68, True),
        "damage_params": _extract_damage_params(msg, 26),
        "restraint_types": _extract_restraint_types(msg),
        "extra_damage_type": _extract_extra_damage_types(msg),
        "cd_info": _extract_cd_info(msg),
        "enhance_info": _extract_enhance_info(msg),
        "cr_damage_params": _extract_cr_damage_params(msg),
        "skill_buff": _extract_skill_buff_info(msg),
        "trans_info": _extract_trans_info(msg),
        "set_cost_info": _extract_set_cost_info(msg),
    })
    _attach_skill_meta(item, sid)
    return item
