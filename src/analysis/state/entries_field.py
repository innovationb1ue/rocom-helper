"""Field and global action-entry handlers for BattleStateTracker."""
from __future__ import annotations

import copy
from typing import Any, Dict

from src.analysis.pet_identity import refresh_battle_uid


def _round(self) -> int:
    return self.state["round"]

def _handle_weather_change_entry(self, entry: Dict[str, Any]) -> None:
    weather_id = entry.get("weather_id")
    weather_name = self._weather_name(weather_id, entry.get("weather_name"))
    weather = {
        "id": weather_id,
        "name": weather_name,
        "expire_round": entry.get("expire_round"),
        "changed_by_skill": entry.get("skill_name") or entry.get("skill_id"),
        "changed_at_round": self.state["round"],
        "skill_id": entry.get("skill_id"),
        "skill_name": entry.get("skill_name"),
        "packet_index": (self._current_event_detail or {}).get("packet_index"),
        "event_ordinal": entry.get("event_ordinal"),
        "opcode": self._current_opcode,
        "parse_quality": (self._current_event_detail or {}).get("parse_quality"),
        "source": (self._current_event_detail or {}).get("schema_message")
            or (self._current_event_detail or {}).get("semantic_level"),
    }
    weather = {k: v for k, v in weather.items() if v is not None}
    self._set_weather_current(weather)
    self._field_context().setdefault("weather_history", []).append(copy.deepcopy(weather))

def _handle_skill_state_entry(self, entry: Dict[str, Any]) -> None:
    caster_pet_id = entry.get("caster_pet_id")
    if caster_pet_id is None:
        return
    for active_key in ("my_active", "opp_active"):
        active = self.state[active_key]
        if active and active.get("pet_id") == caster_pet_id:
            active.setdefault("skill_states", []).append({
                "state_code": entry.get("state_code"),
                "round": self.state["round"],
            })
            return

def _handle_role_skill_cast_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("role_skill_casts", []).append({
        "caster_uin": entry.get("caster_uin"),
        "skill_id": entry.get("skill_id"),
        "pet_id": entry.get("pet_id"),
        "is_call_success": entry.get("is_call_success"),
        "round": self.state["round"],
    })
    if entry.get("is_call_success") and entry.get("pet_id"):
        for active_key in ("my_active", "opp_active"):
            active = self.state[active_key]
            if active and active.get("pet_id") == entry["pet_id"]:
                sid = entry.get("skill_id")
                if sid:
                    used = active.setdefault("used_skills", [])
                    if not any(s.get("skill_id") == sid for s in used):
                        item = {"skill_id": sid}
                        if entry.get("skill_name"):
                            item["skill_name"] = entry["skill_name"]
                        used.append(item)
                break

def _handle_special_move_entry(self, entry: Dict[str, Any]) -> None:
    pet_id = entry.get("pet_id")
    if pet_id is None:
        return
    for active_key in ("my_active", "opp_active"):
        active = self.state[active_key]
        if active and active.get("pet_id") == pet_id:
            active.setdefault("special_moves", []).append({
                "special_move_id": entry.get("special_move_id"),
                "type": entry.get("special_move_type"),
                "round": entry.get("round") or self.state["round"],
                "skill_id": entry.get("skill_id"),
            })
            return

def _handle_skill_pos_change_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("skill_pos_changes", []).append({
        "pet_id": entry.get("pet_id"),
        "skill_pos_infos": entry.get("skill_pos_infos", []),
        "round": self.state["round"],
    })

def _handle_sp_energy_change_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("sp_energy_log", []).append({
        "sp_change_type": entry.get("sp_change_type"),
        "sp_element": entry.get("sp_element"),
        "sp_change_src": entry.get("sp_change_src"),
        "caster_id": entry.get("caster_id"),
        "target_id": entry.get("target_id"),
        "change_value": entry.get("change_value"),
        "real_change_value": entry.get("real_change_value"),
        "round": self.state["round"],
    })

def _handle_sp_energy_trigger_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("sp_energy_triggers", []).append({
        "old_skill_id": entry.get("old_skill_id"),
        "new_skill_id": entry.get("new_skill_id"),
        "trigger_type": entry.get("trigger_type"),
        "round": self.state["round"],
    })

def _handle_idle_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("idle_events", []).append({
        "idle_pet_id": entry.get("idle_pet_id"),
        "round": self.state["round"],
    })

def _handle_notify_perform_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("notifications", []).append({
        "notify_type": entry.get("notify_type"),
        "notify_data": entry.get("notify_data"),
        "tips_id": entry.get("tips_id"),
        "params": entry.get("params"),
        "uin": entry.get("uin"),
        "round": self.state["round"],
    })

def _handle_change_model_entry(self, entry: Dict[str, Any]) -> None:
    pet_id = entry.get("pet_id") or entry.get("original_pet_id")
    model = {
        "kind": "change_model",
        "pet_id": pet_id,
        "old_base_id": entry.get("old_base_id") or entry.get("original_base_conf_id"),
        "model_pet_id": entry.get("model_pet_id"),
        "model_base_id": entry.get("model_base_id"),
        "model_pet_name": entry.get("model_pet_name"),
        "model_battle_stats": entry.get("model_battle_stats"),
        "model_current_hp": entry.get("model_current_hp"),
        "model_max_hp": entry.get("model_max_hp"),
        "role_magic_flag": entry.get("role_magic_flag"),
        "round": self.state["round"],
    }
    model = {k: v for k, v in model.items() if v is not None}
    self.state.setdefault("model_changes", []).append(model)
    if pet_id is None:
        return
    for active_key in ("my_active", "opp_active"):
        active = self.state.get(active_key)
        if active and active.get("pet_id") == pet_id:
            active.setdefault("model_history", []).append(model)
            if entry.get("model_pet_name"):
                active["model_name"] = entry["model_pet_name"]
            if entry.get("model_base_id") is not None:
                active["model_base_id"] = entry["model_base_id"]
            stats = entry.get("model_battle_stats") or []
            if len(stats) >= 6 and stats[5]:
                active["base_speed"] = stats[5]
            if entry.get("model_max_hp") is not None:
                active["max_hp"] = entry["model_max_hp"]
            if entry.get("model_current_hp") is not None:
                self._apply_hp_update(
                    active,
                    event_kind="change_model",
                    entry=entry,
                    side=active.get("side"),
                    target_pet_id=active.get("pet_id"),
                    hp_result=entry["model_current_hp"],
                    source_hint="change_model",
                )
            if active.get("max_hp", 0) > 0 and active.get("current_hp") is not None:
                active["hp_pct"] = active["current_hp"] / active["max_hp"]
            break

def _handle_data_update_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("data_updates", []).append({
        "uin": entry.get("uin"),
        "pet_id": entry.get("pet_id"),
        "pet_skill_updates": entry.get("pet_skill_updates"),
        "round": self.state["round"],
    })
    self._apply_pet_skill_updates(entry)

def _handle_ai_action_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("ai_actions", []).append({
        "pet_id": entry.get("pet_id"),
        "uin": entry.get("uin"),
        "ai_type": entry.get("ai_type"),
        "param": entry.get("param"),
        "round": self.state["round"],
    })

def _handle_supply_pet_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("supply_pet_events", []).append({
        "player_id": entry.get("player_id"),
        "supply_pets": entry.get("supply_pets", []),
        "round": self.state["round"],
    })
    for supplied in entry.get("supply_pets", []) or []:
        side_value = supplied.get("pet_id")
        side_num = self._side_int(side_value)
        if side_num is None:
            continue
        is_mine = self._is_mine(side_num)
        pet_list = self.state["my_pets"] if is_mine else self.state["opp_pets"]
        mapped = self._battle_side_pets.get(side_num)
        matched = mapped if mapped is not None and (
            mapped.get("current_hp", 0) > 0
            or (mapped.get("pet_id") is None and mapped.get("slot") == side_num)
        ) else None
        if matched is None:
            for pet in pet_list:
                if pet.get("slot") == side_num and (
                    pet.get("current_hp", 0) > 0
                    or pet.get("pet_id") is None
                ):
                    matched = pet
                    break
        if matched is None and is_mine and 1 <= side_num <= len(pet_list):
            matched = pet_list[side_num - 1]
        if matched is None:
            matched = {
                "pet_id": None,
                "name": "我方" if is_mine else "敌方",
                "types": [],
                "current_hp": 0,
                "max_hp": 0,
                "hp_pct": 0.0,
                "energy": 10,
                "buffs": [],
                "initial_buff_ids": [],
                "innate_skill_id": None,
                "level": None,
                "slot": side_num,
                "side": 1 if is_mine else 401,
                "stats": [],
                "skills": [],
                "equipped_skills": [],
                "base_id": None,
                "base_conf_id": None,
                "base_skill_pool": None,
                "combo_bonus": 0,
                "poison_stacks": 0,
                "used_skills": [],
                "base_speed": None,
                "protocol_name": None,
                "supply_placeholder": True,
                "pending_supply_side": side_num,
            }
            refresh_battle_uid(matched, side=1 if is_mine else 401)
            pet_list.append(matched)
        self.state["my_active" if is_mine else "opp_active"] = matched
        self._bind_battle_side(side_num, matched, is_mine=is_mine)

def _handle_cmd_failed_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("cmd_failed_events", []).append({
        "failed_reason": entry.get("failed_reason"),
        "round": self.state["round"],
    })

def _handle_runaway_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("runaway_events", []).append({
        "actor_side": entry.get("actor_side"),
        "target_side": entry.get("target_side"),
        "round": self.state["round"],
    })

def _handle_use_item_entry(self, entry: Dict[str, Any]) -> None:
    self.state.setdefault("use_item_events", []).append({
        "caster_id": entry.get("caster_id"),
        "target_id": entry.get("target_id"),
        "item_id": entry.get("item_id"),
        "round": self.state["round"],
    })
