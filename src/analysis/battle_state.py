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

from typing import Any, Dict, List, Optional

from src.analysis.state_helpers import (
    pick_keys,
)
from src.analysis.state import (
    action_resolve,
    entries_damage,
    entries_effects,
    entries_field,
    entries_pet,
    event_dispatch,
    field_events,
    lifecycle_events,
    pet_runtime,
    side_resolver,
    skill_runtime,
    weather,
    wrapper_sync,
)
from src.analysis.state.context import BattleStateContext
from src.analysis.state.hp_ledger import apply_hp_update, as_int, next_ledger_id
from src.analysis.state.lifecycle import build_initial_state
from src.analysis.state.pet_sync import side_int
from src.analysis.state.snapshot import build_state_snapshot, compute_effective_speed

POISON_BUFF_IDS = {20070010}
GLOBAL_EVENT_KINDS = field_events.GLOBAL_EVENT_KINDS


def _compute_effective_speed(pet: Dict[str, Any]) -> Optional[int]:
    """兼容旧测试/调用方的导入名，实际实现位于 state_helpers。"""
    return compute_effective_speed(pet)


class BattleStateTracker:
    def __init__(self) -> None:
        self.state: Dict[str, Any] = build_initial_state()
        # battle slot IDs whose ownership has been established
        self._opponent_slots: set = set()
        self._player_slots: set = set()
        self._battle_side_pets: Dict[int, Dict[str, Any]] = {}
        self._current_opcode: Optional[int] = None
        self._current_event_detail: Dict[str, Any] = {}
        self._ctx = BattleStateContext(
            state=self.state,
            battle_side_pets=self._battle_side_pets,
            player_slots=self._player_slots,
            opponent_slots=self._opponent_slots,
        )

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
        event_dispatch.apply_protocol_event(self, opcode, detail)
        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        return build_state_snapshot(self.state)

    def _field_context(self) -> Dict[str, Any]:
        return self._ctx.field_context()

    _weather_name = staticmethod(weather.weather_name)
    _set_weather_current = weather.set_weather_current

    @staticmethod
    def _append_bounded(items: List[Dict[str, Any]], item: Dict[str, Any], limit: int) -> None:
        BattleStateContext.append_bounded(items, item, limit)

    _global_event_base = field_events.global_event_base
    _global_event_payload = field_events.global_event_payload
    _record_global_event = field_events.record_global_event
    _record_perform_group = field_events.record_perform_group
    _record_sync_event = field_events.record_sync_event
    _record_item_sync_events = field_events.record_item_sync_events

    def _next_ledger_id(self) -> str:
        return next_ledger_id(self)

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:
        return as_int(value)

    def _apply_hp_update(
        self,
        pet: Optional[Dict[str, Any]],
        *,
        event_kind: str,
        entry: Optional[Dict[str, Any]] = None,
        side: Any = None,
        target_pet_id: Any = None,
        hp_change: Any = None,
        hp_result: Any = None,
        target_hp_after: Any = None,
        actual_damage: Any = None,
        source_hint: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return apply_hp_update(
            self,
            pet,
            event_kind=event_kind,
            entry=entry,
            side=side,
            target_pet_id=target_pet_id,
            hp_change=hp_change,
            hp_result=hp_result,
            target_hp_after=target_hp_after,
            actual_damage=actual_damage,
            source_hint=source_hint,
        )

    _pet_for_sync_id = side_resolver.pet_for_sync_id

    _skill_runtime_key = staticmethod(skill_runtime.skill_runtime_key)
    _update_skill_runtime = skill_runtime.update_skill_runtime
    _skill_dam_type = staticmethod(skill_runtime.skill_dam_type)
    _is_internal_leader_skill = staticmethod(skill_runtime.is_internal_leader_skill)
    _skill_source_index = staticmethod(skill_runtime.skill_source_index)
    _normalize_battle_skill_pool = staticmethod(skill_runtime.normalize_battle_skill_pool)
    _apply_battle_skill_pool = staticmethod(skill_runtime.apply_battle_skill_pool)

    _apply_pet_sync = pet_runtime.apply_pet_sync
    _apply_pet_info_sync = pet_runtime.apply_pet_info_sync
    _apply_wrapper_runtime_fields = staticmethod(pet_runtime.apply_wrapper_runtime_fields)
    _enrich_wrapper_buff_for_pet = staticmethod(pet_runtime.enrich_wrapper_buff_for_pet)
    _apply_entry_sync_data = pet_runtime.apply_entry_sync_data
    _apply_pet_skill_updates = pet_runtime.apply_pet_skill_updates

    @staticmethod
    def _pick(entry: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
        return pick_keys(entry, keys)

    pet_name_by_slot = side_resolver.pet_name_by_slot
    _stable_pet_matches = staticmethod(side_resolver.stable_pet_matches)

    def get_suggestions(self) -> List[Dict[str, str]]:
        """基于当前状态给出实时建议。委托给 battle_advisor.build_state_suggestions。"""
        from src.analysis.suggestions import build_state_suggestions
        return build_state_suggestions(self.state)

    _handle_battle_enter = lifecycle_events.handle_battle_enter
    _handle_round_start = lifecycle_events.handle_round_start
    _handle_action_ack = lifecycle_events.handle_action_ack

    _is_mine = side_resolver.is_mine
    _side_int = staticmethod(side_int)
    _bind_battle_side = side_resolver.bind_battle_side
    _set_active_pet = side_resolver.set_active_pet
    _resolve_pet_for_side = side_resolver.resolve_pet_for_side

    _handle_action_resolve = action_resolve.handle_action_resolve
    _handle_damage_entry = entries_damage._handle_damage_entry
    _handle_skill_cast_entry = entries_damage._handle_skill_cast_entry
    _handle_combo_skill_cast_entry = entries_damage._handle_combo_skill_cast_entry
    _handle_defeat_entry = entries_damage._handle_defeat_entry
    _handle_heal_entry = entries_damage._handle_heal_entry
    _handle_energy_entry = entries_damage._handle_energy_entry
    _handle_change_pet_entry = entries_pet._handle_change_pet_entry
    _handle_effect_apply_entry = entries_effects._handle_effect_apply_entry
    _handle_effect_stage_entry = entries_effects._handle_effect_stage_entry
    _append_pet_effect_history = entries_effects._append_pet_effect_history
    _handle_effect_link_entry = entries_effects._handle_effect_link_entry
    _handle_effect_trigger_entry = entries_effects._handle_effect_trigger_entry
    _handle_buff_trigger_entry = entries_effects._handle_buff_trigger_entry
    _is_generic_reflect_trigger = staticmethod(entries_effects._is_generic_reflect_trigger)
    _record_reflect_candidates = entries_effects._record_reflect_candidates
    _attach_reflect_confirmed_effect = entries_effects._attach_reflect_confirmed_effect
    _handle_weather_change_entry = entries_field._handle_weather_change_entry
    _handle_skill_state_entry = entries_field._handle_skill_state_entry
    _handle_role_skill_cast_entry = entries_field._handle_role_skill_cast_entry
    _handle_special_move_entry = entries_field._handle_special_move_entry
    _handle_skill_pos_change_entry = entries_field._handle_skill_pos_change_entry
    _handle_sp_energy_change_entry = entries_field._handle_sp_energy_change_entry
    _handle_sp_energy_trigger_entry = entries_field._handle_sp_energy_trigger_entry
    _handle_idle_entry = entries_field._handle_idle_entry
    _handle_notify_perform_entry = entries_field._handle_notify_perform_entry
    _handle_change_model_entry = entries_field._handle_change_model_entry
    _handle_data_update_entry = entries_field._handle_data_update_entry
    _handle_ai_action_entry = entries_field._handle_ai_action_entry
    _handle_supply_pet_entry = entries_field._handle_supply_pet_entry
    _handle_cmd_failed_entry = entries_field._handle_cmd_failed_entry
    _handle_runaway_entry = entries_field._handle_runaway_entry
    _handle_use_item_entry = entries_field._handle_use_item_entry

    _get_active_for_side = side_resolver.get_active_for_side





    _handle_battle_finish = lifecycle_events.handle_battle_finish
    _handle_skill_select = lifecycle_events.handle_skill_select
    _handle_special_refresh = lifecycle_events.handle_special_refresh
    _handle_skill_declare = lifecycle_events.handle_skill_declare
    _handle_round_flow = lifecycle_events.handle_round_flow
    _pet_matches = staticmethod(wrapper_sync.pet_matches)
    _update_pets_from_wrappers = wrapper_sync.update_pets_from_wrappers
