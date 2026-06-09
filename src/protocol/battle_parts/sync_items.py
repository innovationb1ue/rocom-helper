"""Generic BattleSyncData item-table extraction helpers."""
from __future__ import annotations

from typing import Any, Dict, List

from src.protocol.battle_parts.sync_common import (
    _extract_buffdata_93_skill,
    _pick_fixed32_float,
    _pick_sync_value,
)
from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    normalize_skill_id,
    skill_name,
)
from src.protocol.battle_schema import _compact_dict


_PET_SYNC_FIELDS = {
    1: ("pet_id", False),
    2: ("hp_change", True),
    3: ("hp_result", True),
    6: ("shield_change", True),
    7: ("shield_result", True),
    8: ("attr_type", False),
    9: ("attr_change", True),
    10: ("attr_result", True),
    11: ("original_damage", True),
    12: ("damage_change", True),
    13: ("damage_result", True),
    14: ("buff_id", False),
    15: ("buff_stack_change", True),
    16: ("buff_stack_result", True),
    17: ("state_bit_change_pos", False),
    25: ("energy_change", True),
    26: ("energy_result", True),
    27: ("state_bit_results", False),
    30: ("instant_kill_change", True),
    31: ("instant_kill_result", True),
    32: ("revive_round", True),
    33: ("revive_rounds", True),
    34: ("charging_skill_id", False),
    35: ("height_change", True),
    36: ("height_result", True),
    38: ("mutation_type", False),
    39: ("max_energy", False),
}

_SKILL_SYNC_FIELDS = {
    1: ("pet_id", False),
    2: ("skill_id", False),
    3: ("damage_param_change", True),
    4: ("damage_param_result", True),
    5: ("cast_cnt_change", True),
    6: ("cast_cnt_result", True),
    7: ("pp_change", True),
    8: ("pp_result", True),
    9: ("cost_energy_change", True),
    10: ("cost_energy_result", True),
    11: ("cost_hp_change", True),
    12: ("cost_hp_result", True),
    13: ("display_hp_result", False),
    14: ("sp_energy_skill", False),
    16: ("damage_param_pet_id", True),
    17: ("state", True),
    18: ("damage_type", True),
}

_ROLE_SYNC_FIELDS = {
    1: ("role_uin", False),
    2: ("role_energy_change", True),
    3: ("role_energy_result", True),
    4: ("item_id", True),
    5: ("remain_use_cnt", True),
    6: ("item_num", True),
    7: ("allow_use_cnt", True),
    8: ("hp_change", True),
    9: ("hp_result", True),
    10: ("pvp_score_change", True),
    11: ("pvp_score_result", True),
    12: ("black_hp_change", True),
    13: ("black_hp_result", True),
    14: ("legend_skill_cast_num", True),
    15: ("allow_use_cnt_inbattle", True),
}

_COMM_SYNC_FIELDS = {
    1: ("sp_energy_type", False),
    2: ("sp_energy_change", True),
    3: ("sp_energy_result", True),
    4: ("final_battle_energy_change", True),
    5: ("final_battle_energy_result", True),
    6: ("b1_phantom_point_change", True),
    7: ("b1_phantom_point_result", True),
}

_ITEM_SYNC_FIELDS = {
    1: ("item_id", False),
    4: ("num", True),
    6: ("remain_use_cnt", True),
    10: ("allow_use_cnt", True),
    11: ("battle_use_time_max", True),
    12: ("battle_use_time_remain", True),
}


def _extract_task_infos(sync: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(sync).get(8, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            "task_id": _pick_sync_value(sub, 1, False),
            "task_state": _pick_sync_value(sub, 2, True),
            "uin": _pick_sync_value(sub, 3, False),
        })
        if item:
            items.append(item)
    return items


def _extract_sync_items(sync: Dict[str, Any], field_no: int, spec: Dict[int, tuple]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(sync).get(field_no, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = {
            name: _pick_sync_value(sub, fn, signed)
            for fn, (name, signed) in spec.items()
        }
        if field_no == 3 and item.get("skill_id") is not None:
            sid = normalize_skill_id(item["skill_id"])
            item["skill_id"] = sid
            item["skill_name"] = skill_name(sid)
            item["hp_per_energy"] = _pick_fixed32_float(sub, 15)
        if field_no == 2:
            state_bits = collect_varints(sub, 27)
            if state_bits:
                item["state_bit_results"] = state_bits
            triggered = [
                _extract_buffdata_93_skill(e["sub"])
                for e in field_groups(sub).get(37, [])
                if e.get("sub") is not None
            ]
            triggered = [x for x in triggered if x]
            if triggered:
                item["triggered_buffs"] = triggered
        item = _compact_dict(item)
        if item:
            items.append(item)
    return items
