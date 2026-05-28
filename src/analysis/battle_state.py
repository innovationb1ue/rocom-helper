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
from src.analysis.pet_identity import is_hidden_pet_id, refresh_battle_uid, same_battle_pet
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
from src.data.loader import enrich_buff_modifiers

logger = logging.getLogger(__name__)

POISON_BUFF_IDS = {20070010}
MAX_SYNC_EVENTS = 300
MAX_PERFORM_GROUPS = 300
GLOBAL_EVENT_KINDS = {
    "weather_change",
    "notify_perform",
    "change_model",
    "data_update",
    "ai_action",
    "supply_pet",
    "effect_trigger",
    "effect_link",
}


def _compute_effective_speed(pet: Dict[str, Any]) -> Optional[int]:
    """计算实际速度 = (基础速度 + 固定修正) * (1 + 百分比修正 + 属性等级修正)，最低 1。"""
    base = pet.get("base_speed")
    if base is None:
        return None
    from src.data.loader import get_buff_stat_modifiers, get_speed_buff_modifiers
    speed_mods = get_speed_buff_modifiers(pet.get("buffs", []))
    stat_mods = get_buff_stat_modifiers(pet.get("buffs", []))
    pct = (speed_mods.get("pct_total", 0.0)
           + stat_mods.get("spd_up", 0.0)
           - stat_mods.get("spd_down", 0.0))
    effective = (base + speed_mods.get("flat_total", 0)) * (1.0 + pct)
    return max(1, int(round(effective)))


class BattleStateTracker:
    def __init__(self) -> None:
        initial_weather = {"id": None, "name": None, "expire_round": None}
        self.state: Dict[str, Any] = {
            "battle_id": None,
            "battle_mode": None,
            "round": 0,
            "max_round": 0,
            "weather": initial_weather,
            "field_context": {
                "weather_current": initial_weather,
                "weather_history": [],
                "global_events": [],
                "perform_groups": [],
                "sync_events": [],
                "item_sync_events": [],
            },
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
        self._battle_side_pets: Dict[int, Dict[str, Any]] = {}
        self._current_opcode: Optional[int] = None
        self._current_event_detail: Dict[str, Any] = {}

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

        self._current_opcode = opcode
        self._current_event_detail = detail
        try:
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
        finally:
            self._current_opcode = None
            self._current_event_detail = {}

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

    def _field_context(self) -> Dict[str, Any]:
        ctx = self.state.setdefault("field_context", {
            "weather_current": self.state.get("weather"),
            "weather_history": [],
            "global_events": [],
        })
        ctx.setdefault("perform_groups", [])
        ctx.setdefault("sync_events", [])
        ctx.setdefault("item_sync_events", [])
        return ctx

    @staticmethod
    def _weather_name(weather_id: Any, fallback: Any = None) -> Any:
        if weather_id is not None:
            try:
                from src.data.loader import get_weather
                weather = get_weather(int(weather_id))
            except (TypeError, ValueError):
                weather = None
            if isinstance(weather, dict) and weather.get("name"):
                return weather["name"]
        return fallback

    def _set_weather_current(self, weather: Dict[str, Any]) -> None:
        self.state["weather"] = weather
        self._field_context()["weather_current"] = weather

    def _global_event_base(self, kind: str, entry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entry = entry or {}
        detail = self._current_event_detail or {}
        out = {
            "round": self.state.get("round", 0),
            "opcode": self._current_opcode if self._current_opcode is not None else detail.get("opcode"),
            "packet_index": detail.get("packet_index", entry.get("packet_index")),
            "event_ordinal": entry.get("event_ordinal"),
            "kind": kind,
            "parse_quality": detail.get("parse_quality") or entry.get("parse_quality"),
            "source": detail.get("schema_message") or detail.get("semantic_level") or entry.get("source"),
        }
        return {k: v for k, v in out.items() if v is not None}

    def _record_global_event(
        self,
        kind: str,
        entry: Dict[str, Any],
        *,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        record = self._global_event_base(kind, entry)
        record.update(payload if payload is not None else self._global_event_payload(kind, entry))
        self._field_context().setdefault("global_events", []).append(record)
        return record

    @staticmethod
    def _append_bounded(items: List[Dict[str, Any]], item: Dict[str, Any], limit: int) -> None:
        items.append(item)
        if len(items) > limit:
            del items[:len(items) - limit]

    def _record_perform_group(self, entry: Dict[str, Any]) -> None:
        payload = self._pick(entry, [
            "type", "kind", "group_id", "cast_moment", "is_group_head",
            "group_ref", "is_last_hit", "exec_index", "event_ordinal",
        ])
        if not payload:
            return
        payload.update({
            "round": self.state.get("round", 0),
            "packet_index": (self._current_event_detail or {}).get("packet_index"),
        })
        payload = {k: v for k, v in payload.items() if v is not None}
        self._append_bounded(
            self._field_context().setdefault("perform_groups", []),
            payload,
            MAX_PERFORM_GROUPS,
        )

    def _record_sync_event(self, entry: Dict[str, Any]) -> None:
        sync_data = entry.get("sync_data") or {}
        if not sync_data:
            return
        payload = self._pick(entry, ["kind", "type", "group_id", "exec_index", "event_ordinal"])
        payload.update({
            "round": self.state.get("round", 0),
            "packet_index": (self._current_event_detail or {}).get("packet_index"),
            "sync_data": copy.deepcopy(sync_data),
        })
        self._append_bounded(
            self._field_context().setdefault("sync_events", []),
            payload,
            MAX_SYNC_EVENTS,
        )

    def _record_item_sync_events(self, entry: Dict[str, Any]) -> None:
        for item in (entry.get("sync_data") or {}).get("item_sync", []) or []:
            payload = {
                "round": self.state.get("round", 0),
                "packet_index": (self._current_event_detail or {}).get("packet_index"),
                "group_id": entry.get("group_id"),
                **copy.deepcopy(item),
            }
            self._append_bounded(
                self._field_context().setdefault("item_sync_events", []),
                {k: v for k, v in payload.items() if v is not None},
                MAX_SYNC_EVENTS,
            )

    def _pet_for_sync_id(self, pet_id: Any) -> Optional[Dict[str, Any]]:
        if pet_id is None:
            return None
        side_num = self._side_int(pet_id)
        if side_num is not None and side_num in self._battle_side_pets:
            pet = self._battle_side_pets[side_num]
            active_key = "my_active" if self._is_mine(side_num) else "opp_active"
            active = self.state.get(active_key)
            if (
                pet.get("current_hp", 0) <= 0
                and active is not None
                and active.get("current_hp", 0) > 0
            ):
                self._bind_battle_side(side_num, active, is_mine=(active_key == "my_active"))
                return active
            return pet
        for pet in self.state["my_pets"] + self.state["opp_pets"]:
            if pet.get("pet_id") == pet_id or pet.get("slot") == pet_id:
                return pet
        if side_num is not None:
            return self._resolve_pet_for_side(side_num, bind_fallback=False)
        return None

    @staticmethod
    def _skill_runtime_key(skill_id: Any) -> str:
        return str(skill_id)

    def _update_skill_runtime(self, pet: Optional[Dict[str, Any]], sync: Dict[str, Any]) -> None:
        if pet is None or sync.get("skill_id") is None:
            return
        skill_id = sync["skill_id"]
        runtime = pet.setdefault("skill_runtime", {})
        item = runtime.setdefault(self._skill_runtime_key(skill_id), {"skill_id": skill_id})
        merged = dict(sync.get("skill_data") or {})
        merged.update({k: v for k, v in sync.items() if k != "skill_data"})
        if merged.get("damage_params"):
            merged["damage_params_by_pet"] = {
                str(dp.get("pet_id")): dp.get("damage_param")
                for dp in merged["damage_params"]
                if dp.get("pet_id") is not None and dp.get("damage_param") is not None
            }
        if merged.get("restraint_types"):
            merged["restraint_types_by_pet"] = {
                str(rt.get("pet_id")): rt.get("restraint_type")
                for rt in merged["restraint_types"]
                if rt.get("pet_id") is not None and rt.get("restraint_type") is not None
            }
        for key in (
            "skill_name", "damage_param_change", "damage_param_result",
            "damage_param_pet_id", "cast_cnt_change", "cast_cnt_result",
            "pp_change", "pp_result", "cost_energy_change", "cost_energy_result",
            "cost_hp_change", "cost_hp_result", "display_hp_result",
            "sp_energy_skill", "hp_per_energy", "state", "type", "cast_cnt",
            "cost_energy", "raw_cost_energy", "equipped_slot", "cd_round",
            "raw_damage", "rule_energy", "rule_damage_param", "effect_damage_param",
            "buff_damage_param", "ex_damage_param", "damage_params",
            "damage_params_by_pet", "restraint_types", "restraint_types_by_pet",
            "cd_info", "enhance_info", "damage_type", "source",
        ):
            if merged.get(key) is not None:
                item[key] = merged[key]
        item["source_round"] = self.state.get("round", 0)
        item["round"] = self.state.get("round", 0)

        runtime_cost = (
            merged.get("cost_energy_result")
            if merged.get("cost_energy_result") is not None
            else merged.get("cost_energy")
        )
        if runtime_cost is None:
            runtime_cost = merged.get("raw_cost_energy")

        # 同步装备技能里的实时能耗和目标参数，供当前回合建议直接使用。
        for skill in pet.get("equipped_skills", []):
            if skill.get("skill_id") != skill_id:
                continue
            if runtime_cost is not None:
                skill["runtime_cost_energy"] = runtime_cost
            if merged.get("damage_params") is not None:
                skill["runtime_damage_params"] = merged["damage_params"]
            if merged.get("restraint_types") is not None:
                skill["runtime_restraint_types"] = merged["restraint_types"]

    def _apply_pet_sync(self, sync: Dict[str, Any]) -> None:
        pet = self._pet_for_sync_id(sync.get("pet_id"))
        if pet is None:
            return
        if sync.get("hp_result") is not None:
            pet["current_hp"] = max(0, sync["hp_result"])
            if pet.get("max_hp", 0) > 0:
                pet["hp_pct"] = pet["current_hp"] / pet["max_hp"]
        if sync.get("energy_result") is not None:
            max_energy = sync.get("max_energy") or pet.get("max_energy") or 10
            pet["energy"] = max(0, min(max_energy, sync["energy_result"]))
        if sync.get("max_energy") is not None:
            pet["max_energy"] = sync["max_energy"]
        if sync.get("state_bit_results") is not None:
            pet["state_bit_results"] = sync["state_bit_results"]
        if sync.get("shield_result") is not None:
            pet["shield"] = sync["shield_result"]
        if sync.get("damage_result") is not None:
            pet["last_damage_result"] = sync["damage_result"]
        if sync.get("original_damage") is not None:
            pet["last_original_damage"] = sync["original_damage"]
        if sync.get("charging_skill_id") is not None:
            pet["charging_skill_id"] = sync["charging_skill_id"]
        if sync.get("instant_kill_result") is not None:
            pet["instant_kill_result"] = sync["instant_kill_result"]
        if sync.get("revive_round") is not None:
            pet["revive_round"] = sync["revive_round"]
        if sync.get("revive_rounds") is not None:
            pet["revive_rounds"] = sync["revive_rounds"]
        if sync.get("triggered_buffs") is not None:
            pet["triggered_buffs"] = sync["triggered_buffs"]
        if sync.get("buff_id") is not None and sync.get("buff_stack_result") is not None:
            buffs = pet.setdefault("buffs", [])
            existing = next((b for b in buffs if b.get("id") == sync["buff_id"]), None)
            if sync["buff_stack_result"] <= 0:
                pet["buffs"] = [b for b in buffs if b.get("id") != sync["buff_id"]]
            elif existing:
                existing["stage"] = sync["buff_stack_result"]
                existing.update(enrich_buff_modifiers(existing))
            else:
                buffs.append(enrich_buff_modifiers({
                    "id": sync["buff_id"],
                    "name": str(sync["buff_id"]),
                    "stage": sync["buff_stack_result"],
                }))

    def _apply_pet_info_sync(self, sync: Dict[str, Any]) -> None:
        pet = self._pet_for_sync_id(sync.get("pet_id"))
        if pet is None:
            return
        for key in ("name", "level", "base_conf_id", "types", "max_hp"):
            if sync.get(key) is not None:
                pet[key] = sync[key]
        if sync.get("equipped_skills"):
            pet["runtime_equipped_skills"] = sync["equipped_skills"]

    def _apply_entry_sync_data(self, entry: Dict[str, Any]) -> None:
        sync_data = entry.get("sync_data") or {}
        if not sync_data:
            return
        self._record_sync_event(entry)
        self._record_item_sync_events(entry)
        for sync in sync_data.get("pet_sync", []):
            self._apply_pet_sync(sync)
        for sync in sync_data.get("skill_sync", []):
            sync.setdefault("source", "skill_sync")
            self._update_skill_runtime(self._pet_for_sync_id(sync.get("pet_id")), sync)
        for sync in sync_data.get("skill_change_sync", []):
            sync.setdefault("source", "skill_change_sync")
            self._update_skill_runtime(self._pet_for_sync_id(sync.get("pet_id")), sync)
        for sync in sync_data.get("pet_info", []):
            self._apply_pet_info_sync(sync)
        # role_sync/comm_sync/task_infos 目前只保留紧凑历史，不主动改宠物状态。

    def _apply_pet_skill_updates(self, entry: Dict[str, Any]) -> None:
        for update in entry.get("pet_skill_updates", []) or []:
            pet = self._pet_for_sync_id(update.get("pet_id"))
            for skill in update.get("skills", []) or []:
                skill.setdefault("source", "data_update.pet_skill")
                self._update_skill_runtime(pet, skill)

    @staticmethod
    def _pick(entry: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
        return {key: entry.get(key) for key in keys if entry.get(key) is not None}

    def _global_event_payload(self, kind: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        common = [
            "type", "index", "phase_arg", "state_arg", "extra_arg",
            "group_id", "cast_moment", "is_group_head", "group_ref",
            "is_last_hit", "exec_index",
        ]
        by_kind = {
            "weather_change": common + [
                "skill_id", "skill_name", "weather_id", "weather_name", "expire_round",
            ],
            "notify_perform": common + [
                "notify_type", "notify_data", "tips_id", "params", "uin",
            ],
            "change_model": common + [
                "pet_id", "old_base_id", "role_magic_flag", "model_pet_id",
                "model_base_id", "model_pet_name", "model_battle_stats",
                "model_current_hp", "model_max_hp", "original_pet_id",
                "original_pet_name", "original_pet_types", "original_pet_level",
                "original_base_conf_id",
            ],
            "data_update": common + ["uin", "pet_id", "pet_skill_updates"],
            "ai_action": common + ["pet_id", "uin", "ai_type", "param"],
            "supply_pet": common + ["player_id", "supply_pets"],
            "effect_trigger": common + [
                "actor_side", "actor_side_name", "target_side", "target_side_name",
                "effect_id", "effect_name",
            ],
            "effect_link": common + [
                "actor_side", "actor_side_name", "target_side", "target_side_name",
                "effect_id", "effect_name",
            ],
        }
        payload = self._pick(entry, by_kind.get(kind, common))
        if kind == "weather_change":
            payload["weather_name"] = self._weather_name(
                payload.get("weather_id"), payload.get("weather_name")
            )
        return payload

    def pet_name_by_slot(self, slot: Any, is_mine: bool) -> Optional[str]:
        side_num = self._side_int(slot)
        if side_num is not None:
            pet = self._battle_side_pets.get(side_num)
            if pet is not None:
                return pet.get("name")
        pet_list = self.state["my_pets"] if is_mine else self.state["opp_pets"]
        for pet in pet_list:
            if pet.get("slot") == slot or pet.get("pet_id") == slot:
                return pet.get("name")
        return None

    @staticmethod
    def _stable_pet_matches(pet: Dict[str, Any], w: Dict[str, Any]) -> bool:
        w_pid = w.get("pet_id") or w.get("pet_gid")
        p_pid = pet.get("pet_id")
        w_pet = {
            "pet_id": w_pid,
            "slot": w.get("slot"),
            "side": w.get("side"),
            "base_conf_id": w.get("base_conf_id"),
            "battle_uid": w.get("battle_uid"),
        }
        if same_battle_pet(pet, w_pet):
            return True
        if p_pid is not None and w_pid is not None and p_pid == w_pid:
            if is_hidden_pet_id(p_pid):
                return pet.get("name") == (w.get("name") or w.get("pet_name"))
            return True
        return False

    def get_suggestions(self) -> List[Dict[str, str]]:
        """基于当前状态给出实时建议。委托给 battle_advisor.build_state_suggestions。"""
        from src.analysis.suggestions import build_state_suggestions
        return build_state_suggestions(self.state)

    def _handle_battle_enter(self, detail: Dict[str, Any]) -> None:
        self._opponent_slots.clear()
        self._player_slots.clear()
        self._battle_side_pets.clear()

        self.state["battle_id"] = detail.get("battle_id")
        self.state["battle_mode"] = detail.get("battle_mode")
        self.state["round"] = detail.get("round", 0)
        self.state["max_round"] = detail.get("max_round", 0)
        self.state["result"] = None
        self.state["events"] = []
        self.state["phase"] = "selecting"

        # Weather
        weather_id = detail.get("weather_id")
        weather_name = self._weather_name(weather_id)
        weather = {
            "id": weather_id,
            "name": weather_name,
            "expire_round": detail.get("weather_expire_round"),
            "changed_at_round": self.state["round"],
            "source": "battle_enter",
        }
        self.state["field_context"] = {
            "weather_current": weather,
            "weather_history": [copy.deepcopy(weather)] if weather_id is not None else [],
            "global_events": [],
            "perform_groups": [],
            "sync_events": [],
            "item_sync_events": [],
        }
        self._set_weather_current(weather)

        wrappers = detail.get("wrappers", [])
        my_pets = []
        opp_pets = []
        for w in wrappers:
            pet_info = PetInfo.from_wrapper(w, default_energy=10).to_dict()
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
                if pet_info.get("slot") is not None:
                    self._bind_battle_side(pet_info["slot"], pet_info, is_mine=True)
            else:
                opp_pets.append(pet_info)
                if pet_info.get("slot") is not None:
                    self._bind_battle_side(pet_info["slot"], pet_info, is_mine=False)

        self.state["my_pets"] = my_pets
        self.state["opp_pets"] = opp_pets
        for pet in my_pets:
            refresh_battle_uid(pet, side=1)
        for pet in opp_pets:
            refresh_battle_uid(pet, side=401)
        if my_pets:
            self.state["my_active"] = my_pets[0]
            self._bind_battle_side(1, my_pets[0], is_mine=True)
        if opp_pets:
            self.state["opp_active"] = opp_pets[0]
            self._bind_battle_side(401, opp_pets[0], is_mine=False)

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
        pet = self._battle_side_pets.get(v)
        if pet is not None:
            return pet in self.state["my_pets"]
        if v in self._opponent_slots:
            return False
        if v in self._player_slots:
            return True
        # Fallback: numeric range when slot mapping is not yet established
        return 1 <= v <= 6

    @staticmethod
    def _side_int(side_value: Any) -> Optional[int]:
        try:
            return int(side_value)
        except (TypeError, ValueError):
            return None

    def _bind_battle_side(self, side_value: Any, pet: Optional[Dict[str, Any]], *, is_mine: Optional[bool] = None) -> None:
        side_num = self._side_int(side_value)
        if side_num is None or pet is None:
            return
        if is_mine is None:
            is_mine = pet in self.state["my_pets"]
        self._battle_side_pets[side_num] = pet
        if is_mine:
            self._player_slots.add(side_num)
            self._opponent_slots.discard(side_num)
        else:
            self._opponent_slots.add(side_num)
            self._player_slots.discard(side_num)

    def _set_active_pet(self, pet: Dict[str, Any]) -> None:
        if pet in self.state["my_pets"]:
            self.state["my_active"] = pet
        elif pet in self.state["opp_pets"]:
            self.state["opp_active"] = pet

    def _resolve_pet_for_side(self, side_value: Any, *, bind_fallback: bool = False) -> Optional[Dict[str, Any]]:
        side_num = self._side_int(side_value)
        if side_num is not None:
            pet = self._battle_side_pets.get(side_num)
            if pet is not None:
                active_key = "my_active" if self._is_mine(side_value) else "opp_active"
                active = self.state.get(active_key)
                if (
                    bind_fallback
                    and pet.get("current_hp", 0) <= 0
                    and active is not None
                    and active.get("current_hp", 0) > 0
                ):
                    self._bind_battle_side(side_num, active, is_mine=(active_key == "my_active"))
                    return active
                return pet
            for candidate in self.state["my_pets"] + self.state["opp_pets"]:
                if candidate.get("slot") == side_num:
                    self._bind_battle_side(side_num, candidate)
                    return candidate

        active_key = "my_active" if self._is_mine(side_value) else "opp_active"
        active = self.state[active_key]
        if bind_fallback and side_num is not None and active is not None and active.get("current_hp", 0) <= 0:
            return None
        if bind_fallback and side_num is not None and active is not None:
            self._bind_battle_side(side_num, active, is_mine=(active_key == "my_active"))
        return active

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
    }

    def _handle_action_resolve(self, detail: Dict[str, Any]) -> None:
        for entry in detail.get("entries", []):
            self._record_perform_group(entry)
            if entry.get("kind") in GLOBAL_EVENT_KINDS:
                self._record_global_event(entry["kind"], entry)
            handler_name = self._ENTRY_HANDLERS.get(entry.get("kind"))
            if handler_name:
                getattr(self, handler_name)(entry)
            self._apply_entry_sync_data(entry)

    def _get_active_for_side(self, side_value: Any) -> Optional[Dict[str, Any]]:
        """根据 side 值获取对应的活跃宠物字典。"""
        return self._resolve_pet_for_side(side_value, bind_fallback=True)

    def _handle_damage_entry(self, entry: Dict[str, Any]) -> None:
        target_side = entry.get("damage_target_side")
        damage = entry.get("damage", 0)
        target_hp = entry.get("target_hp_after")
        if target_side is None:
            return
        # damage_target_side is the pet receiving damage — route to its active
        active = self._resolve_pet_for_side(target_side, bind_fallback=True)
        if active is not None:
            # Use target_hp_after only if it's valid (not exceeding max_hp)
            max_hp = active.get("max_hp", 0)
            if target_hp is not None and (max_hp <= 0 or target_hp <= max_hp):
                active["current_hp"] = max(0, target_hp)
            else:
                active["current_hp"] = max(0, active["current_hp"] - damage)
            if active.get("max_hp", 0) > 0:
                active["hp_pct"] = active["current_hp"] / active["max_hp"]
            else:
                active["hp_pct"] = 1.0 if active["current_hp"] > 0 else 0.0
            self._set_active_pet(active)

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
                skill_name = entry.get("skill_name")
                if not skill_name:
                    from src.data.loader import get_skill_name
                    skill_name = get_skill_name(skill_id)
                if skill_name:
                    used.append({"skill_id": skill_id, "skill_name": skill_name})
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
            active["current_hp"] = min(hp_after, active["max_hp"])
            active["hp_pct"] = active["current_hp"] / active["max_hp"]

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
        new_base_conf_id = entry.get("new_pet_base_conf_id")
        if battle_pet_id is None:
            return

        # 判断换宠发生在哪方。target_side 1-6/401-406 在不同对局中可能反转
        # （取决于谁是房主），所以优先用已知宠物列表交叉验证。
        is_opp = None

        # 1. 用 rest_pet_id（被换下的宠物）匹配已知列表
        rest_pet_id = entry.get("rest_pet_id")
        if rest_pet_id is not None:
            for pet in self.state["opp_pets"]:
                if pet.get("pet_id") == rest_pet_id or pet.get("base_conf_id") == rest_pet_id:
                    is_opp = True
                    break
            if is_opp is None:
                for pet in self.state["my_pets"]:
                    if pet.get("pet_id") == rest_pet_id or pet.get("base_conf_id") == rest_pet_id:
                        is_opp = False
                        break

        # 2. 用 new_pet_id 匹配已知列表（换上的宠物可能已知）
        if is_opp is None and new_pet_id is not None and new_pet_id != 20000000:
            for pet in self.state["opp_pets"]:
                if pet.get("pet_id") == new_pet_id:
                    is_opp = True
                    break
            if is_opp is None:
                for pet in self.state["my_pets"]:
                    if pet.get("pet_id") == new_pet_id:
                        is_opp = False
                        break

        # 3. 已知的 slot 映射
        if is_opp is None:
            bpid = int(battle_pet_id)
            if bpid in self._opponent_slots:
                is_opp = True
            elif bpid in self._player_slots:
                is_opp = False

        # 4. 用当前活跃宠物判断（换宠替换的是活跃宠物）
        if is_opp is None and rest_pet_id is not None:
            active = self.state.get("opp_active")
            if active and (active.get("pet_id") == rest_pet_id or active.get("base_conf_id") == rest_pet_id):
                is_opp = True
        if is_opp is None and rest_pet_id is not None:
            active = self.state.get("my_active")
            if active and (active.get("pet_id") == rest_pet_id or active.get("base_conf_id") == rest_pet_id):
                is_opp = False

        # 5. Fallback: target_side numeric range
        if is_opp is None:
            target_side = entry.get("target_side")
            if target_side is not None:
                is_opp = int(target_side) >= 401

        # 6. Final fallback: battle_pet_id range
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
        # 优先用 base_conf_id 匹配（始终可用，即使 pet_id=20000000）
        if new_base_conf_id is not None:
            for pet in pet_list:
                if pet.get("base_conf_id") == new_base_conf_id:
                    matched = pet
                    break
        # 其次用 pet_id 匹配（对手可能在之前的 change_pet 中已更新真实 conf_id）
        if matched is None and new_pet_id is not None and new_pet_id != 20000000:
            for pet in pet_list:
                if pet.get("pet_id") == new_pet_id:
                    matched = pet
                    break
        # 名称匹配作为兜底
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
            if matched.get("side") is None:
                matched["side"] = 401 if is_opp else 1
            if matched.get("slot") is None:
                matched["slot"] = battle_pet_id
            # 如果获得了真实的 conf_id，更新宠物记录（从 20000000 更新为真实值）
            if new_pet_id is not None and new_pet_id != 20000000:
                if matched.get("pet_id") == 20000000:
                    matched["pet_id"] = new_pet_id
            # 同样更新 base_conf_id
            if new_base_conf_id is not None and matched.get("base_conf_id") is None:
                matched["base_conf_id"] = new_base_conf_id
            refresh_battle_uid(matched, side=401 if is_opp else 1)
            self.state[active_key] = matched
            self._bind_battle_side(battle_pet_id, matched, is_mine=not is_opp)
            target_side = entry.get("target_side")
            if target_side is not None:
                self._bind_battle_side(target_side, matched, is_mine=not is_opp)
            matched["buffs"] = []
            matched["combo_bonus"] = 0
            matched["poison_stacks"] = 0
            # 保留该宠物已曝光技能；换下再换上时不应丢失历史追踪
            matched.setdefault("used_skills", [])
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
                existing.update(enrich_buff_modifiers(existing))
            existing["turns_applied"] = existing.get("turns_applied", 0) + 1
        else:
            buffs.append(enrich_buff_modifiers({
                "id": effect_id,
                "name": ename or str(effect_id),
                "stage": stage,
                "source_skill": (entry.get("related_skills") or [{}])[0].get("skill_name") if entry.get("related_skills") else None,
                "turns_applied": 1,
            }))
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
                existing.update(enrich_buff_modifiers(existing))

    def _append_pet_effect_history(self, entry: Dict[str, Any], event_kind: str) -> None:
        side = entry.get("target_side") or entry.get("actor_side")
        active = self._get_active_for_side(side) if side is not None else None
        target = active if active is not None else self.state
        target.setdefault("effect_history", []).append({
            "kind": event_kind,
            "effect_id": entry.get("effect_id"),
            "effect_name": entry.get("effect_name"),
            "effect_base": entry.get("effect_base"),
            "actor_side": entry.get("actor_side"),
            "target_side": entry.get("target_side"),
            "round": self.state["round"],
            "event_ordinal": entry.get("event_ordinal"),
        })

    def _handle_effect_link_entry(self, entry: Dict[str, Any]) -> None:
        self._append_pet_effect_history(entry, "effect_link")

    def _handle_effect_trigger_entry(self, entry: Dict[str, Any]) -> None:
        self._append_pet_effect_history(entry, "effect_trigger")

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
                if entry.get("model_current_hp") is not None:
                    active["current_hp"] = entry["model_current_hp"]
                if entry.get("model_max_hp") is not None:
                    active["max_hp"] = entry["model_max_hp"]
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
    # 活跃指针：通过 base_conf_id 或名称匹配当前活跃宠物
    def _update_pets_from_wrappers(self, wrappers: List[Dict[str, Any]]) -> None:
        active_candidates: Dict[str, Dict[str, Any]] = {}
        active_sides: Dict[str, Any] = {}
        active_ownership: Dict[str, bool] = {}
        for w in wrappers:
            side = w.get("side")
            is_mine = (side == 1 or side == "我方")
            pet_list = self.state["my_pets"] if is_mine else self.state["opp_pets"]
            pet_id = w.get("pet_id") or w.get("pet_gid")
            matched = None
            for pet in pet_list:
                if self._stable_pet_matches(pet, w):
                    matched = pet
                    if "hp" in w:
                        new_hp = w["hp"]
                        if is_mine or new_hp is None or new_hp <= pet.get("current_hp", float("inf")):
                            pet["current_hp"] = new_hp if new_hp is not None else pet["current_hp"]
                    if "max_hp" in w:
                        pet["max_hp"] = w["max_hp"]
                    if w.get("name") and w["name"] != "?":
                        pet["name"] = w["name"]
                    if w.get("pet_id") and w["pet_id"] != 20000000:
                        pet["pet_id"] = w["pet_id"]
                    if w.get("level") is not None:
                        pet["level"] = w["level"]
                    new_stats = w.get("stats")
                    if new_stats and len(new_stats) >= len(pet.get("stats", [])):
                        pet["stats"] = new_stats
                    if w.get("base_id") is not None:
                        pet["base_id"] = w["base_id"]
                    if w.get("base_conf_id") is not None:
                        pet["base_conf_id"] = w["base_conf_id"]
                    if w.get("slot") is not None:
                        pet["slot"] = w["slot"]
                    if w.get("side") is not None:
                        pet["side"] = w["side"]
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
                                pet.setdefault("buffs", []).append(enrich_buff_modifiers(b))
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
                    # 能量刷新（PetData.field 33）。None = 未设置（battle_enter），跳过
                    wrapper_energy = w.get("energy")
                    if wrapper_energy is not None and wrapper_energy > 0:
                        pet["energy"] = min(10, wrapper_energy)
                    # 属性类型（仅首次为空时填充）
                    if not pet.get("types") and w.get("types"):
                        pet["types"] = w["types"]
                    if pet["max_hp"] > 0:
                        pet["hp_pct"] = pet["current_hp"] / pet["max_hp"]
                    refresh_battle_uid(pet)
                    break
            if matched is None:
                pet_info = PetInfo.from_wrapper(w).to_dict()
                refresh_battle_uid(pet_info)
                pet_list.append(pet_info)
                matched = pet_list[-1]
            # round_start wrapper 仅包含当前出战精灵，是活跃指针的权威数据
            active_key = "my_active" if is_mine else "opp_active"
            if matched is not None:
                current_candidate = active_candidates.get(active_key)
                if current_candidate is None:
                    active_candidates[active_key] = matched
                    active_sides[active_key] = side
                    active_ownership[active_key] = is_mine
                elif current_candidate.get("current_hp", 0) <= 0 and matched.get("current_hp", 0) > 0:
                    active_candidates[active_key] = matched
                    active_sides[active_key] = side
                    active_ownership[active_key] = is_mine
        for active_key, pet in active_candidates.items():
            self.state[active_key] = pet
            self._bind_battle_side(
                active_sides.get(active_key),
                pet,
                is_mine=active_ownership.get(active_key),
            )
