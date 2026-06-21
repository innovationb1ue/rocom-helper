"""BattlePerformInfo entry dispatch and container summary helpers."""
from __future__ import annotations

from typing import Any, Dict, List

from src.protocol.proto_core import (
    buff_name,
    collect_varints,
    field_groups,
    first_sub,
    pick_first,
)
from src.protocol.battle_parts import perform_generic
from src.protocol.battle_parts.perform_entries_core import (
    apply_damage_entry,
    apply_energy_entry,
    apply_heal_entry,
    apply_skill_cast_entry,
)
from src.protocol.battle_parts.perform_entries_effects import (
    apply_buff_trigger_entry,
    apply_effect_apply_entry,
    apply_effect_link_entry,
    apply_effect_trigger_entry,
)
from src.protocol.battle_parts.perform_entries_field import (
    apply_ai_action_entry,
    apply_data_update_entry,
    apply_idle_entry,
    apply_notify_perform_entry,
    apply_pvp_perform_marker_entry,
    apply_skill_state_entry,
    apply_weather_change_entry,
)
from src.protocol.battle_parts.perform_entries_pet import (
    apply_change_model_entry,
    apply_change_pet_entry,
    apply_defeat_entry,
    apply_revive_entry,
    apply_supply_pet_entry,
)
from src.protocol.battle_parts.perform_entries_resource import (
    apply_sp_energy_change_entry,
    apply_sp_energy_trigger_entry,
)
from src.protocol.battle_parts.perform_entries_skill import (
    apply_combo_skill_cast_entry,
    apply_role_skill_cast_entry,
    apply_skill_pos_change_entry,
    apply_special_move_entry,
)
from src.protocol.battle_parts.sync import _extract_sync_data


def _attach_perform_meta(out: Dict[str, Any], sub: Dict[str, Any]) -> None:
    """补充 BattlePerformInfo 的通用元信息和同步结果。"""
    is_group_head = pick_first(collect_varints(sub, 11))
    is_last_hit = pick_first(collect_varints(sub, 27))
    out.update({
        "type": pick_first(collect_varints(sub, 1)),
        "index": pick_first(collect_varints(sub, 2)),
        "group_id": pick_first(collect_varints(sub, 2)),
        "is_group_head": bool(is_group_head) if is_group_head is not None else None,
        "phase_arg": pick_first(collect_varints(sub, 14)),
        "cast_moment": pick_first(collect_varints(sub, 14)),
        "state_arg": pick_first(collect_varints(sub, 26)),
        "group_ref": pick_first(collect_varints(sub, 26)),
        "extra_arg": is_last_hit,
        "is_last_hit": bool(is_last_hit) if is_last_hit is not None else None,
        "event_ordinal": pick_first(collect_varints(sub, 39)),
        "exec_index": pick_first(collect_varints(sub, 39)),
    })
    sync_data = _extract_sync_data(first_sub(field_groups(sub).get(12, [])))
    if sync_data:
        out["sync_data"] = sync_data


def _extract_1324_entry(sub: Dict[str, Any]) -> Dict[str, Any]:
    """Extract a single action entry from a 0x1324 sub-message."""
    sg = field_groups(sub)
    entry_type = pick_first(collect_varints(sub, 1))
    out: Dict[str, Any] = {}
    _attach_perform_meta(out, sub)

    if entry_type == 1:
        apply_skill_cast_entry(out, sg)
    elif entry_type == 4:
        apply_damage_entry(out, sg)
    elif entry_type == 2:
        apply_effect_apply_entry(out, sg)
    elif entry_type == 3:
        apply_buff_trigger_entry(out, sg)
    elif entry_type == 7:
        apply_defeat_entry(out, sg)
    elif entry_type == 10:
        apply_effect_link_entry(out, sg)
    elif entry_type == 5:
        apply_heal_entry(out, sg)
    elif entry_type == 6:
        apply_energy_entry(out, sg)
    elif entry_type == 8:
        apply_revive_entry(out, sg)
    elif entry_type == 9:
        apply_effect_trigger_entry(out, sg)
    elif entry_type == 11:
        apply_sp_energy_change_entry(out, sg)
    elif entry_type == 12:
        apply_sp_energy_trigger_entry(out, sg)
    elif entry_type == 13:
        apply_change_pet_entry(out, sg)
    elif entry_type == 15:
        apply_idle_entry(out, sg)
    elif entry_type == 19:
        apply_skill_state_entry(out, sg)
    elif entry_type == 22:
        apply_weather_change_entry(out, sg)
    elif entry_type == 23:
        apply_notify_perform_entry(out, sg)
    elif entry_type == 24:
        apply_change_model_entry(out, sg)
    elif entry_type == 29:
        apply_role_skill_cast_entry(out, sg)
    elif entry_type == 30:
        apply_combo_skill_cast_entry(out, sg)
    elif entry_type == 25:
        apply_ai_action_entry(out, sg)
    elif entry_type == 34:
        apply_pvp_perform_marker_entry(out, sg)
    elif entry_type == 35:
        apply_data_update_entry(out, sg)
    elif entry_type == 37:
        apply_supply_pet_entry(out, sg)
    elif entry_type == 38:
        apply_skill_pos_change_entry(out, sg)
    elif entry_type == 39:
        apply_special_move_entry(out, sg)
    else:
        perform_generic.apply_generic_perform_entry(out, entry_type, sub)

    return out


def _extract_perform_cmd(container: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all entries from a perform-command container and build a summary."""
    c_groups = field_groups(container)

    packet_state = pick_first(collect_varints(container, 1))
    packet_phase = pick_first(collect_varints(container, 3))
    packet_index = pick_first(collect_varints(container, 5))

    entries: List[Dict[str, Any]] = []
    for f2_entry in c_groups.get(2, []):
        sub = f2_entry.get("sub")
        if sub is not None:
            entries.append(_extract_1324_entry(sub))

    effect_ids = sorted({int(it["effect_id"]) for it in entries if it.get("effect_id") is not None})
    effect_names = [buff_name(eid) or str(eid) for eid in effect_ids]

    return {
        "packet_state": packet_state,
        "packet_phase": packet_phase,
        "packet_index": packet_index,
        "entries": entries,
        "primary_skill": next((it for it in entries if it.get("skill_id")), None),
        "energy_event": next((it for it in entries if it.get("kind") == "skill_cast"), None),
        "damage_event": next((it for it in entries if it.get("kind") == "damage"), None),
        "effect_ids": effect_ids,
        "effect_names": effect_names,
        "has_defeat": any(it.get("kind") == "defeat" for it in entries),
        "opcode": record.get("opcode"),
        "opcode_hex": record.get("opcode_hex", ""),
    }
