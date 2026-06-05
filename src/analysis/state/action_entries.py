"""Action-entry classification helpers for BattleStateTracker."""
from __future__ import annotations

from typing import Dict


ENTRY_HANDLERS: Dict[str, str] = {
    "damage": "_handle_damage_entry",
    "skill_cast": "_handle_skill_cast_entry",
    "combo_skill_cast": "_handle_combo_skill_cast_entry",
    "defeat": "_handle_defeat_entry",
    "heal": "_handle_heal_entry",
    "energy": "_handle_energy_entry",
    "change_pet": "_handle_change_pet_entry",
    "effect_apply": "_handle_effect_apply_entry",
    "effect_stage": "_handle_effect_stage_entry",
    "buff_trigger": "_handle_buff_trigger_entry",
    "effect_link": "_handle_effect_link_entry",
    "effect_trigger": "_handle_effect_trigger_entry",
    "weather_change": "_handle_weather_change_entry",
    "skill_state": "_handle_skill_state_entry",
    "role_skill_cast": "_handle_role_skill_cast_entry",
    "special_move": "_handle_special_move_entry",
    "skill_pos_change": "_handle_skill_pos_change_entry",
    "sp_energy_change": "_handle_sp_energy_change_entry",
    "sp_energy_trigger": "_handle_sp_energy_trigger_entry",
    "idle": "_handle_idle_entry",
    "notify_perform": "_handle_notify_perform_entry",
    "change_model": "_handle_change_model_entry",
    "data_update": "_handle_data_update_entry",
    "ai_action": "_handle_ai_action_entry",
    "supply_pet": "_handle_supply_pet_entry",
    "cmd_failed": "_handle_cmd_failed_entry",
    "runaway": "_handle_runaway_entry",
    "use_item": "_handle_use_item_entry",
}
