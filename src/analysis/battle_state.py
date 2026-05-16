"""实时战斗状态追踪器 — 消费协议事件，维护战斗状态。

BattleStateTracker 维护一个完整的战斗状态字典，包含：
- 双方精灵列表 (my_pets / opp_pets) 和当前活跃精灵 (my_active / opp_active)
- 战斗元信息 (battle_id, round, phase, weather)
- 完整事件历史 (events)

通过 handle_event(opcode, detail) 接收协议事件，根据 opcode 分发到对应的处理函数。
支持的 opcode: 0x1316(进入), 0x131A(回合开始), 0x1324(行动结算), 0x132C(结束),
               0x130B(技能选择), 0x13F4(特殊刷新), 0x1322(技能声明), 0x1312(回合流)

战斗阶段: idle → selecting → resolving → (循环 resolving) → finished
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

from src.analysis.pet_info import PetInfo
from src.analysis.constants import (
    OPCODE_ACTION_RESOLVE,
    OPCODE_BATTLE_ENTER,
    OPCODE_BATTLE_FINISH,
    OPCODE_ROUND_FLOW,
    OPCODE_ROUND_START,
    OPCODE_SKILL_DECLARE,
    OPCODE_SKILL_SELECT,
    OPCODE_SPECIAL_REFRESH,
)

logger = logging.getLogger(__name__)

POISON_BUFF_IDS = {20070010}


def _compute_effective_speed(pet: Dict[str, Any]) -> Optional[int]:
    """计算实际速度 = (基础速度 + 固定修正) * (1 + 百分比修正)，最低 1。"""
    base = pet.get("base_speed")
    if base is None:
        return None
    from src.data.loader import get_speed_buff_modifiers
    mods = get_speed_buff_modifiers(pet.get("buffs", []))
    effective = (base + mods.get("flat_total", 0)) * (1.0 + mods.get("pct_total", 0.0))
    return max(1, int(round(effective)))


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
        # battle slot IDs whose ownership has been established
        self._opponent_slots: set = set()
        self._player_slots: set = set()

    def handle_event(self, opcode: int, detail: Dict[str, Any]) -> Dict[str, Any]:
        """处理协议事件，更新状态，返回最新快照。

        Opcode 分发表:
          0x1316 = 进入战斗 → 初始化双方精灵、天气、阶段设为 selecting
          0x131A = 回合开始 → 更新精灵状态、阶段设为 resolving
          0x1324 = 行动结算 → 处理伤害/效果/换宠/击杀等子事件
          0x132C = 战斗结束 → 设置结果、阶段设为 finished
          0x130B = 技能选择 → 客户端意图（仅记录）
          0x13F4 = 特殊刷新 → 能量瓶等特殊操作
          0x1322 = 技能声明 → 服务端确认（仅记录）
          0x1312 = 回合流 → 更新回合号
        """
        event = {"opcode": opcode, "round": self.state["round"]}
        event.update(detail)
        self.state["events"].append(event)

        if opcode == OPCODE_BATTLE_ENTER:
            self._handle_battle_enter(detail)
        elif opcode == OPCODE_ROUND_START:
            self._handle_round_start(detail)
        elif opcode == OPCODE_ACTION_RESOLVE:
            self._handle_action_resolve(detail)
        elif opcode == OPCODE_BATTLE_FINISH:
            self._handle_battle_finish(detail)
        elif opcode == OPCODE_SKILL_SELECT:
            self._handle_skill_select(detail)
        elif opcode == OPCODE_SPECIAL_REFRESH:
            self._handle_special_refresh(detail)
        elif opcode == OPCODE_SKILL_DECLARE:
            self._handle_skill_declare(detail)
        elif opcode == OPCODE_ROUND_FLOW:
            self._handle_round_flow(detail)

        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        state = copy.deepcopy(self.state)
        # 计算所有精灵的实际速度（基础速度 + buff 修正）
        for pet in state.get("my_pets", []) + state.get("opp_pets", []):
            pet["effective_speed"] = _compute_effective_speed(pet)
        for key in ("my_active", "opp_active"):
            active = state.get(key)
            if active:
                active["effective_speed"] = _compute_effective_speed(active)
        return state

    def pet_name_by_slot(self, slot: Any, is_mine: bool) -> Optional[str]:
        pet_list = self.state["my_pets"] if is_mine else self.state["opp_pets"]
        for pet in pet_list:
            if pet.get("slot") == slot or pet.get("pet_id") == slot:
                return pet.get("name")
        return None

    def get_suggestions(self) -> List[Dict[str, str]]:
        """基于当前状态给出实时建议。委托给 battle_advisor.build_state_suggestions。"""
        from src.analysis.battle_advisor import build_state_suggestions
        return build_state_suggestions(self.state)

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
            pet_info = PetInfo.from_wrapper(w, default_energy=5).to_dict()
            equipped = w.get("equipped_skills") or []
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

    def _is_mine(self, side_value) -> bool:
        """True if *side_value* represents the player side."""
        if side_value is None:
            return False
        if isinstance(side_value, str):
            return side_value == "我方"
        v = int(side_value)
        if v in self._opponent_slots:
            return False
        if v in self._player_slots:
            return True
        # Fallback: numeric range when slot mapping is not yet established
        return 1 <= v <= 6

    # _handle_action_resolve 是最复杂的状态更新函数。
    # 遍历 detail["entries"] 列表，按 entry.kind 分派处理:
    #   damage → 更新目标 HP
    #   skill_cast → 记录使用技能、更新能量
    #   combo_skill_cast → 记录连击加成
    #   defeat → 标记精灵 HP=0
    #   heal → 恢复 HP
    #   energy → 更新能量值
    #   change_pet → 切换活跃精灵（匹配: pet_id → name → slot → 新建）
    #   effect_apply → 添加/更新 buff
    #   effect_stage → 更新 buff 阶段

    _ENTRY_HANDLERS = {
        "damage": "_handle_damage_entry",
        "skill_cast": "_handle_skill_cast_entry",
        "combo_skill_cast": "_handle_combo_skill_cast_entry",
        "defeat": "_handle_defeat_entry",
        "heal": "_handle_heal_entry",
        "energy": "_handle_energy_entry",
        "change_pet": "_handle_change_pet_entry",
        "effect_apply": "_handle_effect_apply_entry",
        "effect_stage": "_handle_effect_stage_entry",
        "weather_change": "_handle_weather_change_entry",
        "skill_state": "_handle_skill_state_entry",
        "role_skill_cast": "_handle_role_skill_cast_entry",
        "special_move": "_handle_special_move_entry",
        "skill_pos_change": "_handle_skill_pos_change_entry",
        "sp_energy_change": "_handle_sp_energy_change_entry",
        "sp_energy_trigger": "_handle_sp_energy_trigger_entry",
        "idle": "_handle_idle_entry",
        "notify_perform": "_handle_notify_perform_entry",
    }

    def _handle_action_resolve(self, detail: Dict[str, Any]) -> None:
        for entry in detail.get("entries", []):
            handler_name = self._ENTRY_HANDLERS.get(entry.get("kind"))
            if handler_name:
                getattr(self, handler_name)(entry)

    def _get_active_for_side(self, side_value: Any) -> Optional[Dict[str, Any]]:
        """根据 side 值获取对应的活跃宠物字典。"""
        active_key = "my_active" if self._is_mine(side_value) else "opp_active"
        return self.state[active_key]

    def _handle_damage_entry(self, entry: Dict[str, Any]) -> None:
        target_side = entry.get("damage_target_side")
        damage = entry.get("damage", 0)
        target_hp = entry.get("target_hp_after")
        if target_side is None:
            return
        # damage_target_side is the pet receiving damage — route to its active
        active_key = "my_active" if self._is_mine(target_side) else "opp_active"
        active = self.state[active_key]
        if active is not None:
            active["current_hp"] = target_hp if target_hp is not None else max(0, active["current_hp"] - damage)
            if active.get("max_hp", 0) > 0:
                active["hp_pct"] = active["current_hp"] / active["max_hp"]
            else:
                active["hp_pct"] = 1.0 if active["current_hp"] > 0 else 0.0

    def _handle_skill_cast_entry(self, entry: Dict[str, Any]) -> None:
        actor_side = entry.get("actor_side", "")
        energy_delta = entry.get("energy_delta", 0)
        energy_after = entry.get("energy_after")
        active = self._get_active_for_side(actor_side)
        if active is None:
            return
        skill_id = entry.get("skill_id")
        if skill_id is not None:
            used = active.setdefault("used_skills", [])
            if not any(s.get("skill_id") == skill_id for s in used):
                item = {"skill_id": skill_id}
                if entry.get("skill_name"):
                    item["skill_name"] = entry["skill_name"]
                used.append(item)
        if energy_after is not None:
            active["energy"] = min(10, energy_after)
        else:
            active["energy"] = min(10, max(0, active.get("energy", 5) + energy_delta))

    def _handle_combo_skill_cast_entry(self, entry: Dict[str, Any]) -> None:
        actor_side = entry.get("actor_side")
        combo_count = entry.get("combo_count")
        if actor_side is not None and combo_count is not None:
            active = self._get_active_for_side(actor_side)
            if active is not None:
                active["combo_bonus"] = combo_count

    def _handle_defeat_entry(self, entry: Dict[str, Any]) -> None:
        defeated_side = entry.get("target_side", "")
        active = self._get_active_for_side(defeated_side)
        if active is not None:
            active["current_hp"] = 0
            active["hp_pct"] = 0.0

    def _handle_heal_entry(self, entry: Dict[str, Any]) -> None:
        target_side = entry.get("target_side")
        hp_after = entry.get("target_hp_after")
        if target_side is None or hp_after is None:
            return
        active = self._get_active_for_side(target_side)
        if active is not None and active["max_hp"] > 0:
            active["current_hp"] = hp_after
            active["hp_pct"] = hp_after / active["max_hp"]

    def _handle_energy_entry(self, entry: Dict[str, Any]) -> None:
        target_side = entry.get("target_side") or entry.get("actor_side")
        energy_after = entry.get("energy_after")
        energy_delta = entry.get("energy_delta")
        if target_side is None:
            return
        active = self._get_active_for_side(target_side)
        if active is not None:
            if energy_after is not None:
                active["energy"] = min(10, energy_after)
            elif energy_delta is not None:
                active["energy"] = min(10, max(0, active.get("energy", 5) + energy_delta))

    def _handle_change_pet_entry(self, entry: Dict[str, Any]) -> None:
        battle_pet_id = entry.get("battle_pet_id")
        new_pet_name = entry.get("new_pet_name")
        new_pet_id = entry.get("new_pet_id")
        if battle_pet_id is None:
            return

        # Determine side by pet identity, not slot number range.
        is_opp = None
        if new_pet_id is not None:
            in_my = any(p.get("pet_id") == new_pet_id for p in self.state["my_pets"])
            in_opp = any(p.get("pet_id") == new_pet_id for p in self.state["opp_pets"])
            if in_my and not in_opp:
                is_opp = False
            elif in_opp and not in_my:
                is_opp = True

        # New pet not in either list: use rest_pet_id (the pet being benched)
        if is_opp is None:
            rest_pet_id = entry.get("rest_pet_id")
            if rest_pet_id in self._opponent_slots:
                is_opp = True
            elif rest_pet_id in self._player_slots:
                is_opp = False

        # Fallback: numeric range
        if is_opp is None:
            bpid = int(battle_pet_id)
            is_opp = bpid >= 401

        # Record slot mapping
        bpid = int(battle_pet_id)
        if is_opp:
            self._opponent_slots.add(bpid)
        else:
            self._player_slots.add(bpid)

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
            matched = PetInfo.from_change_pet(entry, battle_pet_id, is_opp).to_dict()
            pet_list.append(matched)
        if matched is not None:
            self.state[active_key] = matched
            matched["buffs"] = []
            matched["combo_bonus"] = 0
            # 用 change_pet wrapper 中的丰富数据更新已匹配的宠物
            if matched.get("base_speed") is None:
                bs = entry.get("new_pet_battle_stats") or []
                if len(bs) >= 6 and bs[5]:
                    matched["base_speed"] = bs[5]
            if entry.get("new_pet_current_hp") is not None and entry.get("new_pet_max_hp") is not None:
                matched["current_hp"] = entry["new_pet_current_hp"]
                matched["max_hp"] = entry["new_pet_max_hp"]
                if matched["max_hp"] > 0:
                    matched["hp_pct"] = matched["current_hp"] / matched["max_hp"]
            if entry.get("new_pet_energy") is not None:
                matched["energy"] = min(10, entry["new_pet_energy"])
            if entry.get("new_pet_passive_skill_id") is not None:
                matched["innate_skill_id"] = entry["new_pet_passive_skill_id"]

    def _handle_effect_apply_entry(self, entry: Dict[str, Any]) -> None:
        target_side = entry.get("target_side")
        effect_id = entry.get("effect_id")
        if target_side is None or effect_id is None:
            return
        active = self._get_active_for_side(target_side)
        if active is None:
            return
        buffs = active.setdefault("buffs", [])
        stage = entry.get("effect_stage")
        ename = entry.get("effect_name")
        # BuffChangeType: 0=NULL, 1=ADD, 2=CHANGE, 3=REMOVE
        if stage == 3:
            # 移除 buff
            active["buffs"] = [b for b in buffs if b.get("id") != effect_id]
            return
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
        if effect_id in POISON_BUFF_IDS:
            active["poison_stacks"] = stage if stage is not None else active.get("poison_stacks", 0) + 1

    def _handle_effect_stage_entry(self, entry: Dict[str, Any]) -> None:
        actor_side = entry.get("actor_side")
        effect_id = entry.get("effect_id")
        new_stage = entry.get("effect_stage")
        if actor_side is None:
            return
        active = self._get_active_for_side(actor_side)
        if active is not None:
            buffs = active.get("buffs", [])
            existing = next((b for b in buffs if b["id"] == effect_id), None)
            if existing and new_stage is not None:
                existing["stage"] = new_stage

    def _handle_weather_change_entry(self, entry: Dict[str, Any]) -> None:
        weather_id = entry.get("weather_id")
        weather_name = entry.get("weather_name")
        if weather_id is not None and weather_name is None:
            from src.data.loader import get_attr_name
            weather_name = get_attr_name(weather_id)
        self.state["weather"] = {
            "id": weather_id,
            "name": weather_name,
            "expire_round": entry.get("expire_round"),
            "changed_by_skill": entry.get("skill_name") or entry.get("skill_id"),
            "changed_at_round": self.state["round"],
        }

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
            "round": self.state["round"],
        })

    def _handle_battle_finish(self, detail: Dict[str, Any]) -> None:
        self.state["result"] = detail.get("result_name", "UNKNOWN")
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
        refresh_kind = detail.get("kind") or detail.get("action_name")
        if refresh_kind in ("energy_bottle", "能量瓶"):
            target_side = detail.get("side")
            active_key = "my_active" if self._is_mine(target_side) else "opp_active"
            active = self.state[active_key]
            if active is not None:
                active["energy"] = min(10, active.get("energy", 5) + detail.get("energy_delta", 3))

    def _handle_skill_declare(self, detail: Dict[str, Any]) -> None:
        skill_id = detail.get("skill_id")
        actor_side = detail.get("actor_side")
        if skill_id is None or actor_side is None:
            return
        active = self._get_active_for_side(actor_side)
        if active is None:
            return
        used = active.setdefault("used_skills", [])
        if not any(s.get("skill_id") == skill_id for s in used):
            item = {"skill_id": skill_id}
            if detail.get("skill_name"):
                item["skill_name"] = detail["skill_name"]
            used.append(item)

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

    # _update_pets_from_wrappers 用回合开始时的 wrapper 数据刷新精灵状态。
    # 匹配逻辑（按优先级）:
    #   1. pet_id 精确匹配（通用对手ID 20000000 需要二次匹配 slot/name）
    #   2. 未匹配则创建新条目
    # 每侧仅第一个 wrapper 更新 active 指针（通过 seen_sides 去重）
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
                    # 刷新先天特性
                    if w.get("passive_skill_id") is not None:
                        pet["innate_skill_id"] = w["passive_skill_id"]
                    # 合并初始 buff（仅添加尚不存在的 buff）
                    w_buffs = w.get("initial_buffs", [])
                    if w_buffs:
                        existing_ids = {b["id"] for b in pet.get("buffs", []) if "id" in b}
                        for b in w_buffs:
                            if b.get("id") not in existing_ids:
                                pet.setdefault("buffs", []).append(b)
                    # 如果之前没有装备技能，用新 wrapper 的补充
                    w_eq = w.get("equipped_skills") or []
                    if w_eq and not pet.get("equipped_skills"):
                        pet["skills"] = w.get("skills", [])
                        pet["equipped_skills"] = w_eq
                    # 从 battle_stats[5] 设置基础速度（仅首次，战斗中不变）
                    if pet.get("base_speed") is None:
                        w_bs = w.get("battle_stats") or []
                        if len(w_bs) >= 6 and w_bs[5]:
                            pet["base_speed"] = w_bs[5]
                    # 能量刷新
                    if w.get("energy") is not None:
                        pet["energy"] = min(10, w["energy"])
                    # 属性类型（仅首次为空时填充）
                    if not pet.get("types") and w.get("types"):
                        pet["types"] = w["types"]
                    if pet["max_hp"] > 0:
                        pet["hp_pct"] = pet["current_hp"] / pet["max_hp"]
                    # Keep active reference pointing to the same dict in pet_list
                    active_key = "my_active" if is_mine else "opp_active"
                    cur_active = self.state[active_key]
                    if cur_active is not None and cur_active.get("pet_id") == pet.get("pet_id"):
                        self.state[active_key] = pet
                    break
            if matched is None:
                pet_info = PetInfo.from_wrapper(w).to_dict()
                pet_list.append(pet_info)
                matched = pet_list[-1]
            # Update active pet only for first wrapper per side
            active_key = "my_active" if is_mine else "opp_active"
            if side not in seen_sides:
                seen_sides.add(side)
                self.state[active_key] = matched
