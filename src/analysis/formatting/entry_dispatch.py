"""0x1324/0x13FC/0x13F3 action entry 格式化分发。"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from src.analysis.formatting.core import FormattedEvent
from src.analysis.formatting.entries_combat import format_damage, format_defeat, format_skill_cast
from src.analysis.formatting.entries_effects import (
    format_buff_trigger,
    format_effect_apply,
    format_effect_link,
    format_effect_stage,
    format_effect_trigger,
)
from src.analysis.formatting.entries_misc import (
    format_ai_action,
    format_cmd_failed,
    format_generic,
    format_idle,
    format_notify_perform,
    format_pvp_perform_marker,
    format_role_skill_cast,
    format_runaway,
    format_skill_pos_change,
    format_skill_state,
    format_special_move,
    format_weather_change,
)
from src.analysis.formatting.entries_pet import (
    format_change_model,
    format_change_pet,
    format_revive,
    format_supply_pet,
)
from src.analysis.formatting.entries_resources import (
    format_energy,
    format_heal,
    format_sp_energy_change,
    format_sp_energy_trigger,
    format_use_item,
)

EntryFormatter = Callable[[Dict[str, Any], Dict[str, Any]], FormattedEvent]

SUPPRESSED_KINDS = {"data_update"}

ENTRY_FORMATTERS: Dict[str, EntryFormatter] = {
    "skill_cast": format_skill_cast,
    "damage": format_damage,
    "defeat": format_defeat,
    "effect_apply": format_effect_apply,
    "effect_stage": format_effect_stage,
    "buff_trigger": format_buff_trigger,
    "effect_link": format_effect_link,
    "heal": format_heal,
    "energy": format_energy,
    "change_pet": format_change_pet,
    "effect_trigger": format_effect_trigger,
    "revive": format_revive,
    "ai_action": format_ai_action,
    "pvp_perform_marker": format_pvp_perform_marker,
    "supply_pet": format_supply_pet,
    "weather_change": format_weather_change,
    "skill_state": format_skill_state,
    "role_skill_cast": format_role_skill_cast,
    "special_move": format_special_move,
    "skill_pos_change": format_skill_pos_change,
    "sp_energy_change": format_sp_energy_change,
    "sp_energy_trigger": format_sp_energy_trigger,
    "idle": format_idle,
    "notify_perform": format_notify_perform,
    "change_model": format_change_model,
    "cmd_failed": format_cmd_failed,
    "runaway": format_runaway,
    "use_item": format_use_item,
}


def format_action_entry(
    entry: Dict[str, Any],
    state: Dict[str, Any],
    round_num: int = 0,
) -> Optional[FormattedEvent]:
    kind = entry.get("kind", "")
    if kind in SUPPRESSED_KINDS:
        return None
    formatter = ENTRY_FORMATTERS.get(kind, format_generic)
    event = formatter(entry, state)
    event.round = round_num
    return event
