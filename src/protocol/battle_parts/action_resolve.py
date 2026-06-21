"""Action/perform opcode extraction for battle protocol."""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.protocol.proto_core import field_groups, first_sub
from src.protocol.battle_parts.perform_dispatch import (
    _extract_1324_entry,
    _extract_perform_cmd,
)


# ---------------------------------------------------------------------------
# 0x1324 / 0x13FC / 0x13F3 - Action / perform containers
# ---------------------------------------------------------------------------
# _extract_1324_entry 由 perform_dispatch 解析 action resolve 中的单个条目。
# entry_type (field 1) 决定条目类型:
#   1=skill_cast, 4=damage, 2=effect_apply, 3=buff_trigger,
#   5=heal, 6=energy, 7=defeat, 8=revive, 9=effect_trigger,
#   10=effect_link, 11=sp_energy_change, 12=sp_energy_trigger,
#   13=change_pet, 15=idle, 19=skill_state, 22=weather_change,
#   23=notify_perform, 25=ai_action, 29=role_skill_cast,
#   30=combo_skill_cast, 34=pvp_perform_marker, 35=data_update,
#   37=supply_pet, 38=skill_pos_change, 39=special_move


def _extract_perform_record(record: Dict[str, Any], extract_kind: str) -> Optional[Dict[str, Any]]:
    root = record.get("root")
    if root is None:
        return None

    groups = field_groups(root)
    container_entries = groups.get(1, [])
    container = first_sub(container_entries)
    if container is None:
        return None

    result = _extract_perform_cmd(container, record)
    result["extract_kind"] = extract_kind
    return result


def extract_1324_action(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract action details from opcode 0x1324."""
    return _extract_perform_record(record, "action")


def extract_13fc_pvp_perform(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract PVP perform details from opcode 0x13FC (same structure as 0x1324)."""
    return _extract_perform_record(record, "pvp_perform")


# ---------------------------------------------------------------------------
# 0x13f3 - Preplay
# ---------------------------------------------------------------------------

def extract_13f3_preplay(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract preplay details from opcode 0x13F3 (same structure as 0x1324)."""
    return _extract_perform_record(record, "preplay")
