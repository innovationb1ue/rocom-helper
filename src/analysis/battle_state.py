"""实时战斗状态追踪器 — 消费协议事件，维护战斗状态。"""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BattleStateTracker:
    def __init__(self) -> None:
        self.state: Dict[str, Any] = {
            "battle_id": None,
            "battle_mode": None,
            "round": 0,
            "max_round": 0,
            "weather": {"id": None, "name": None, "expire_round": None},
            "phase": "idle",
            "my_pets": [],
            "opp_pets": [],
            "my_active": None,
            "opp_active": None,
            "events": [],
            "result": None,
        }

    def handle_event(self, opcode: int, detail: Dict[str, Any]) -> Dict[str, Any]:
        """处理协议事件，更新状态，返回最新快照。"""
        event = {"opcode": opcode, "round": self.state["round"]}
        event.update(detail)
        self.state["events"].append(event)

        if opcode == 0x1316:
            self._handle_battle_enter(detail)
        elif opcode == 0x131A:
            self._handle_round_start(detail)
        elif opcode == 0x1324:
            self._handle_action_resolve(detail)
        elif opcode == 0x132C:
            self._handle_battle_finish(detail)
        elif opcode == 0x130B:
            self._handle_skill_select(detail)
        elif opcode == 0x13F4:
            self._handle_special_refresh(detail)
        elif opcode == 0x1322:
            self._handle_skill_declare(detail)
        elif opcode == 0x1312:
            self._handle_round_flow(detail)

        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        return copy.deepcopy(self.state)

    def pet_name_by_slot(self, slot: Any, is_mine: bool) -> Optional[str]:
        pet_list = self.state["my_pets"] if is_mine else self.state["opp_pets"]
        for pet in pet_list:
            if pet.get("slot") == slot or pet.get("pet_id") == slot:
                return pet.get("name")
        return None

    def get_suggestions(self) -> List[Dict[str, str]]:
        """基于当前状态给出实时建议。"""
        suggestions: List[Dict[str, str]] = []
        seen: set = set()
        my_active = self.state["my_active"]
        opp_active = self.state["opp_active"]

        if my_active is None or opp_active is None:
            return suggestions

        my_hp_pct = my_active.get("hp_pct", 1.0)
        if my_hp_pct < 0.25:
            suggestions.append({"type": "low_hp", "message": "我方精灵HP过低，考虑换宠"})
        if my_hp_pct > 0.75:
            suggestions.append({"type": "hp_ok", "message": "我方精灵HP健康"})

        opp_hp_pct = opp_active.get("hp_pct", 1.0)
        if opp_hp_pct < 0.25:
            suggestions.append({"type": "finish_off", "message": "对手精灵HP极低，可尝试击杀"})

        if my_active.get("energy", 0) < 2:
            suggestions.append({"type": "low_energy", "message": "能量不足，考虑使用低能耗技能或能量瓶"})

        my_buffs = my_active.get("buffs", [])
        negative_buffs = [b for b in my_buffs if b.get("stacks", 0) < 0]
        if len(negative_buffs) >= 2:
            suggestions.append({"type": "debuffed", "message": "我方精灵有多个负面状态"})

        # Deduplicate by (type, message)
        unique: List[Dict[str, str]] = []
        for s in suggestions:
            key = (s["type"], s["message"])
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique

    def _handle_battle_enter(self, detail: Dict[str, Any]) -> None:
        self.state["battle_id"] = detail.get("battle_id")
        self.state["battle_mode"] = detail.get("battle_mode")
        self.state["round"] = detail.get("round", 0)
        self.state["max_round"] = detail.get("max_round", 0)
        self.state["result"] = None
        self.state["events"] = []
        self.state["phase"] = "selecting"

        # Weather
        weather_id = detail.get("weather_id")
        weather_name = None
        if weather_id is not None:
            from src.data.loader import get_attr_name
            weather_name = get_attr_name(weather_id)
        self.state["weather"] = {
            "id": weather_id,
            "name": weather_name,
            "expire_round": detail.get("weather_expire_round"),
        }

        wrappers = detail.get("wrappers", [])
        my_pets = []
        opp_pets = []
        for w in wrappers:
            equipped = w.get("equipped_skills") or []
            pet_info = {
                "pet_id": w.get("pet_id") or w.get("pet_gid"),
                "name": w.get("pet_name") or w.get("name", "?"),
                "types": w.get("types", []),
                "current_hp": w.get("hp") or w.get("current_hp", 0),
                "max_hp": w.get("max_hp", 0),
                "energy": 5,
                "buffs": [],
                "level": w.get("level"),
                "slot": w.get("slot"),
                "side": w.get("side"),
                "stats": w.get("stats", []),
                "skills": w.get("skills", []),
                "equipped_skills": equipped,
                "base_id": w.get("base_id"),
                "base_skill_pool": w.get("base_skill_pool"),
            }
            if pet_info["max_hp"] > 0:
                pet_info["hp_pct"] = pet_info["current_hp"] / pet_info["max_hp"]
            else:
                pet_info["hp_pct"] = 1.0
            side = w.get("side")
            side_label = "MY" if (side == 1 or side == "我方") else "OPP"
            logger.info(
                "[%s] %s: %d equipped skills (source=%s) %s",
                side_label, pet_info["name"], len(equipped),
                w.get("skill_source", "?"),
                [s.get("skill_name", "?") for s in equipped],
            )
            if side == 1 or side == "我方":
                my_pets.append(pet_info)
            else:
                opp_pets.append(pet_info)

        self.state["my_pets"] = my_pets

        self.state["my_pets"] = my_pets
        self.state["opp_pets"] = opp_pets
        if my_pets:
            self.state["my_active"] = my_pets[0]
        if opp_pets:
            self.state["opp_active"] = opp_pets[0]

    def _handle_round_start(self, detail: Dict[str, Any]) -> None:
        self.state["round"] = detail.get("round", self.state["round"] + 1)
        self.state["phase"] = "resolving"
        wrappers = detail.get("wrappers", [])
        self._update_pets_from_wrappers(wrappers)

    @staticmethod
    def _is_mine(side_value) -> bool:
        """True if *side_value* represents the player side."""
        if side_value is None:
            return False
        if isinstance(side_value, str):
            return side_value == "我方"
        v = int(side_value)
        return 1 <= v <= 6

    def _handle_action_resolve(self, detail: Dict[str, Any]) -> None:
        entries = detail.get("entries", [])
        for entry in entries:
            kind = entry.get("kind")
            if kind == "damage":
                target_side = entry.get("damage_target_side")
                damage = entry.get("damage", 0)
                target_hp = entry.get("target_hp_after")
                is_opp = not self._is_mine(target_side)
                active_key = "opp_active" if is_opp else "my_active"
                active = self.state[active_key]
                if active is not None:
                    active["current_hp"] = target_hp if target_hp is not None else max(0, active["current_hp"] - damage)
                    if active["max_hp"] > 0:
                        active["hp_pct"] = active["current_hp"] / active["max_hp"]

            elif kind == "skill_cast":
                actor_side = entry.get("actor_side", "")
                energy_delta = entry.get("energy_delta", 0)
                energy_after = entry.get("energy_after")
                active_key = "my_active" if self._is_mine(actor_side) else "opp_active"
                active = self.state[active_key]
                if active is not None:
                    # 记录使用过的技能
                    skill_id = entry.get("skill_id")
                    if skill_id is not None:
                        used = active.setdefault("used_skills", [])
                        if not any(s.get("skill_id") == skill_id for s in used):
                            item = {"skill_id": skill_id}
                            if entry.get("skill_name"):
                                item["skill_name"] = entry["skill_name"]
                            used.append(item)
                    if energy_after is not None:
                        active["energy"] = energy_after
                    else:
                        active["energy"] = max(0, active.get("energy", 5) + energy_delta)

            elif kind == "defeat":
                defeated_side = entry.get("target_side", "")
                is_mine = self._is_mine(defeated_side)
                active_key = "my_active" if is_mine else "opp_active"
                active = self.state[active_key]
                if active is not None:
                    active["current_hp"] = 0
                    active["hp_pct"] = 0.0

            elif kind == "heal":
                target_side = entry.get("target_side")
                hp_after = entry.get("target_hp_after")
                if target_side is not None and hp_after is not None:
                    is_mine = self._is_mine(target_side)
                    active_key = "my_active" if is_mine else "opp_active"
                    active = self.state[active_key]
                    if active is not None and active["max_hp"] > 0:
                        active["current_hp"] = hp_after
                        active["hp_pct"] = hp_after / active["max_hp"]

            elif kind == "energy":
                target_side = entry.get("target_side") or entry.get("actor_side")
                energy_after = entry.get("energy_after")
                energy_delta = entry.get("energy_delta")
                if target_side is not None:
                    is_mine = self._is_mine(target_side)
                    active_key = "my_active" if is_mine else "opp_active"
                    active = self.state[active_key]
                    if active is not None:
                        if energy_after is not None:
                            active["energy"] = energy_after
                        elif energy_delta is not None:
                            active["energy"] = max(0, active.get("energy", 5) + energy_delta)

            elif kind == "change_pet":
                battle_pet_id = entry.get("battle_pet_id")
                new_pet_name = entry.get("new_pet_name")
                new_pet_id = entry.get("new_pet_id")
                new_pet_types = entry.get("new_pet_types", [])
                new_pet_level = entry.get("new_pet_level")
                if battle_pet_id is not None:
                    is_opp = int(battle_pet_id) >= 401
                    pet_list = self.state["opp_pets"] if is_opp else self.state["my_pets"]
                    active_key = "opp_active" if is_opp else "my_active"
                    active = self.state[active_key]
                    if active is not None:
                        entry["_prev_active_name"] = active.get("name", "?")
                    matched = None
                    # Match by real pet_id
                    if new_pet_id is not None:
                        for pet in pet_list:
                            if pet.get("pet_id") == new_pet_id:
                                matched = pet
                                break
                    # Match by name
                    if matched is None and new_pet_name:
                        for pet in pet_list:
                            if pet.get("name") == new_pet_name:
                                matched = pet
                                break
                    # Match by slot position (player slots 1-6 map to index 0-5)
                    if matched is None and not is_opp:
                        idx = int(battle_pet_id) - 1
                        if 0 <= idx < len(pet_list):
                            matched = pet_list[idx]
                    # Not found — create a new pet entry from extracted data
                    if matched is None and new_pet_name:
                        matched = {
                            "pet_id": new_pet_id,
                            "name": new_pet_name,
                            "types": new_pet_types,
                            "current_hp": 0,
                            "max_hp": 0,
                            "energy": 5,
                            "buffs": [],
                            "slot": battle_pet_id,
                            "level": new_pet_level,
                            "side": 401 if is_opp else 1,
                        }
                        pet_list.append(matched)
                    if matched is not None:
                        self.state[active_key] = matched
                        matched["buffs"] = []

            elif kind == "effect_apply":
                target_side = entry.get("target_side")
                effect_id = entry.get("effect_id")
                if target_side is not None and effect_id is not None:
                    is_mine = self._is_mine(target_side)
                    active_key = "my_active" if is_mine else "opp_active"
                    active = self.state[active_key]
                    if active is not None:
                        buffs = active.setdefault("buffs", [])
                        stage = entry.get("effect_stage")
                        ename = entry.get("effect_name")
                        existing = next((b for b in buffs if b["id"] == effect_id), None)
                        if existing:
                            if stage is not None:
                                existing["stage"] = stage
                            existing["turns_applied"] = existing.get("turns_applied", 0) + 1
                        else:
                            buffs.append({
                                "id": effect_id,
                                "name": ename or str(effect_id),
                                "stage": stage,
                                "source_skill": (entry.get("related_skills") or [{}])[0].get("skill_name") if entry.get("related_skills") else None,
                                "turns_applied": 1,
                            })

            elif kind == "effect_stage":
                actor_side = entry.get("actor_side")
                effect_id = entry.get("effect_id")
                new_stage = entry.get("effect_stage")
                if actor_side is not None:
                    is_mine = self._is_mine(actor_side)
                    active_key = "my_active" if is_mine else "opp_active"
                    active = self.state[active_key]
                    if active is not None:
                        buffs = active.get("buffs", [])
                        existing = next((b for b in buffs if b["id"] == effect_id), None)
                        if existing and new_stage is not None:
                            existing["stage"] = new_stage

    def _handle_battle_finish(self, detail: Dict[str, Any]) -> None:
        self.state["result"] = detail.get("result_name", "UNKNOWN")
        self.state["phase"] = "finished"
        self.state["phase"] = "finished"
        finish_pets = detail.get("finish_pet_infos", [])
        for fp in finish_pets:
            pet_id = fp.get("pet_gid")
            remain = fp.get("remain_hp", 0)
            for pet in self.state["my_pets"] + self.state["opp_pets"]:
                if pet.get("pet_id") == pet_id:
                    pet["current_hp"] = remain
                    if pet["max_hp"] > 0:
                        pet["hp_pct"] = remain / pet["max_hp"]

    def _handle_skill_select(self, detail: Dict[str, Any]) -> None:
        pass  # Client intent, just logged

    def _handle_special_refresh(self, detail: Dict[str, Any]) -> None:
        refresh_kind = detail.get("kind")
        if refresh_kind == "energy_bottle":
            target_side = detail.get("side")
            active_key = "my_active" if self._is_mine(target_side) else "opp_active"
            active = self.state[active_key]
            if active is not None:
                active["energy"] = min(10, active.get("energy", 5) + detail.get("energy_delta", 3))

    def _handle_skill_declare(self, detail: Dict[str, Any]) -> None:
        pass  # Server skill declare, just logged

    def _handle_round_flow(self, detail: Dict[str, Any]) -> None:
        self.state["round"] = detail.get("round", self.state["round"])

    @staticmethod
    def _pet_matches(pet: Dict[str, Any], w: Dict[str, Any]) -> bool:
        """Match a wrapper to an existing pet.  Uses pet_id first; for PvP
        opponents with a generic id (e.g. 20000000), falls back to slot then name."""
        w_pid = w.get("pet_id") or w.get("pet_gid")
        p_pid = pet.get("pet_id")
        if p_pid is not None and w_pid is not None and p_pid == w_pid:
            # generic opponent id — need secondary match
            if p_pid == 20000000:
                w_slot = w.get("slot")
                p_slot = pet.get("slot")
                if w_slot is not None and p_slot is not None and w_slot == p_slot:
                    return True
                return pet.get("name") == w.get("name")
            return True
        return False

    def _update_pets_from_wrappers(self, wrappers: List[Dict[str, Any]]) -> None:
        seen_sides: set = set()
        for w in wrappers:
            side = w.get("side")
            is_mine = (side == 1 or side == "我方")
            pet_list = self.state["my_pets"] if is_mine else self.state["opp_pets"]
            pet_id = w.get("pet_id") or w.get("pet_gid")
            matched = None
            for pet in pet_list:
                if self._pet_matches(pet, w):
                    matched = pet
                    if "hp" in w:
                        pet["current_hp"] = w["hp"]
                    if "max_hp" in w:
                        pet["max_hp"] = w["max_hp"]
                    if w.get("name") and w["name"] != "?":
                        pet["name"] = w["name"]
                    if w.get("pet_id") and w["pet_id"] != 20000000:
                        pet["pet_id"] = w["pet_id"]
                    if w.get("level") is not None:
                        pet["level"] = w["level"]
                    if w.get("stats"):
                        pet["stats"] = w["stats"]
                    if w.get("base_id") is not None:
                        pet["base_id"] = w["base_id"]
                    if w.get("base_skill_pool") is not None:
                        pet["base_skill_pool"] = w["base_skill_pool"]
                    # 如果之前没有装备技能，用新 wrapper 的补充
                    w_eq = w.get("equipped_skills") or []
                    if w_eq and not pet.get("equipped_skills"):
                        pet["skills"] = w.get("skills", [])
                        pet["equipped_skills"] = w_eq
                    if pet["max_hp"] > 0:
                        pet["hp_pct"] = pet["current_hp"] / pet["max_hp"]
                    break
            if matched is None:
                pet_info = {
                    "pet_id": pet_id,
                    "name": w.get("name", "?"),
                    "types": w.get("types", []),
                    "current_hp": w.get("hp") or w.get("current_hp", 0),
                    "max_hp": w.get("max_hp", 0),
                    "energy": w.get("energy", 5),
                    "buffs": [],
                    "slot": w.get("slot"),
                    "level": w.get("level"),
                    "side": w.get("side"),
                    "stats": w.get("stats", []),
                    "skills": w.get("skills", []),
                    "equipped_skills": w.get("equipped_skills", []),
                    "base_id": w.get("base_id"),
                    "base_skill_pool": w.get("base_skill_pool"),
                }
                if pet_info["max_hp"] > 0:
                    pet_info["hp_pct"] = pet_info["current_hp"] / pet_info["max_hp"]
                else:
                    pet_info["hp_pct"] = 1.0
                pet_list.append(pet_info)
                matched = pet_list[-1]
            # Update active pet only for first wrapper per side
            active_key = "my_active" if is_mine else "opp_active"
            if side not in seen_sides:
                seen_sides.add(side)
                self.state[active_key] = matched
