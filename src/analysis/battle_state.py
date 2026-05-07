"""实时战斗状态追踪器 — 消费协议事件，维护战斗状态。"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional


class BattleStateTracker:
    def __init__(self) -> None:
        self.state: Dict[str, Any] = {
            "battle_id": None,
            "battle_mode": None,
            "round": 0,
            "max_round": 0,
            "weather_id": None,
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

    def get_suggestions(self) -> List[Dict[str, str]]:
        """基于当前状态给出实时建议。"""
        suggestions: List[Dict[str, str]] = []
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

        return suggestions

    def _handle_battle_enter(self, detail: Dict[str, Any]) -> None:
        self.state["battle_id"] = detail.get("battle_id")
        self.state["battle_mode"] = detail.get("battle_mode")
        self.state["round"] = detail.get("round", 0)
        self.state["max_round"] = detail.get("max_round", 0)
        self.state["weather_id"] = detail.get("weather_id")
        self.state["result"] = None
        self.state["events"] = []

        wrappers = detail.get("wrappers", [])
        my_pets = []
        opp_pets = []
        for w in wrappers:
            pet_info = {
                "pet_id": w.get("pet_id") or w.get("pet_gid"),
                "name": w.get("pet_name") or w.get("name", "?"),
                "types": w.get("types", []),
                "current_hp": w.get("hp") or w.get("current_hp", 0),
                "max_hp": w.get("max_hp", 0),
                "energy": 5,
                "buffs": [],
            }
            if pet_info["max_hp"] > 0:
                pet_info["hp_pct"] = pet_info["current_hp"] / pet_info["max_hp"]
            else:
                pet_info["hp_pct"] = 1.0
            side = w.get("side")
            if side == 1 or side == "我方":
                my_pets.append(pet_info)
            else:
                opp_pets.append(pet_info)

        self.state["my_pets"] = my_pets
        self.state["opp_pets"] = opp_pets
        if my_pets:
            self.state["my_active"] = my_pets[0]
        if opp_pets:
            self.state["opp_active"] = opp_pets[0]

    def _handle_round_start(self, detail: Dict[str, Any]) -> None:
        self.state["round"] = detail.get("round", self.state["round"] + 1)
        wrappers = detail.get("wrappers", [])
        self._update_pets_from_wrappers(wrappers)

    def _handle_action_resolve(self, detail: Dict[str, Any]) -> None:
        entries = detail.get("entries", [])
        for entry in entries:
            kind = entry.get("kind")
            if kind == "damage":
                target_side = entry.get("damage_target_side")
                damage = entry.get("damage", 0)
                target_hp = entry.get("target_hp_after")

                pet_list = self.state["opp_pets"] if target_side == "敌方" else self.state["my_pets"]
                active_key = "opp_active" if target_side == "敌方" else "my_active"
                active = self.state[active_key]
                if active is not None:
                    active["current_hp"] = target_hp if target_hp is not None else max(0, active["current_hp"] - damage)
                    if active["max_hp"] > 0:
                        active["hp_pct"] = active["current_hp"] / active["max_hp"]

            elif kind == "skill_cast":
                actor_side = entry.get("actor_side", "")
                energy_delta = entry.get("energy_delta", 0)
                energy_after = entry.get("energy_after")
                active_key = "my_active" if actor_side == "我方" else "opp_active"
                active = self.state[active_key]
                if active is not None:
                    if energy_after is not None:
                        active["energy"] = energy_after
                    else:
                        active["energy"] = max(0, active.get("energy", 5) + energy_delta)

            elif kind == "defeat":
                defeated_side = entry.get("actor_side", "")
                pet_list_key = "my_pets" if defeated_side == "我方" else "opp_pets"
                active_key = "my_active" if defeated_side == "我方" else "opp_active"
                active = self.state[active_key]
                if active is not None:
                    active["current_hp"] = 0
                    active["hp_pct"] = 0.0

    def _handle_battle_finish(self, detail: Dict[str, Any]) -> None:
        self.state["result"] = detail.get("result_name", "UNKNOWN")
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
            active_key = "my_active" if target_side == "我方" else "opp_active"
            active = self.state[active_key]
            if active is not None:
                active["energy"] = min(10, active.get("energy", 5) + detail.get("energy_delta", 3))

    def _handle_skill_declare(self, detail: Dict[str, Any]) -> None:
        pass  # Server skill declare, just logged

    def _handle_round_flow(self, detail: Dict[str, Any]) -> None:
        self.state["round"] = detail.get("round", self.state["round"])

    def _update_pets_from_wrappers(self, wrappers: List[Dict[str, Any]]) -> None:
        for w in wrappers:
            side = w.get("side")
            pet_list = self.state["my_pets"] if (side == 1 or side == "我方") else self.state["opp_pets"]
            pet_id = w.get("pet_id") or w.get("pet_gid")
            for pet in pet_list:
                if pet.get("pet_id") == pet_id:
                    if "hp" in w:
                        pet["current_hp"] = w["hp"]
                    if "max_hp" in w:
                        pet["max_hp"] = w["max_hp"]
                    if pet["max_hp"] > 0:
                        pet["hp_pct"] = pet["current_hp"] / pet["max_hp"]
                    break
