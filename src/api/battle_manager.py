"""全局战斗状态管理器 — 单例模式，桥接嗅探器与 WebSocket 客户端。

BattleManager 是整个战斗分析管线的中枢:
1. 维护 BattleStateTracker 实例（战斗状态）
2. 管理 WebSocket 客户端连接列表
3. 注册嗅探器回调，实时处理战斗数据包
4. 协调事件格式化、伤害分析、钩子分发

通过 get_battle_manager() 全局访问（单例模式）。

处理流程:
  sniffer 回调 → _on_sniffer_record → process_event
    → tracker.handle_event (更新状态)
    → format_battle_event (格式化事件)
    → _push_state / _push_events (推送 WebSocket)
    → _push_damage_analysis (伤害预测)
    → _run_analysis_hooks (钩子分析)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from src.analysis.battle_state import BattleStateTracker
from src.analysis.event_formatter import format_battle_event, compute_battle_summary

logger = logging.getLogger(__name__)


class BattleManager:
    """管理战斗状态、WebSocket 连接和事件处理。

    通过 get_battle_manager() 从任何模块全局访问。
    """

    _LIFECYCLE_OPCODES = {0x1316, 0x131A, 0x132C, 0x0102}
    _IN_BATTLE_OPCODES = {
        0x130B, 0x1322, 0x1324, 0x13F4, 0x130C,
        0x01A9, 0x0220, 0x13FC, 0x13F3, 0x1312,
        0x1326, 0x132A, 0x132D, 0x1334, 0x133C, 0x13F6,
    }

    def __init__(self) -> None:
        self._tracker: Optional[BattleStateTracker] = None
        self._ws_clients: List[WebSocket] = []
        self._bridge_registered = False
        self._advisor: Optional[Any] = None
        self._hook_registry: Optional[Any] = None

    @property
    def tracker(self) -> Optional[BattleStateTracker]:
        return self._tracker

    @property
    def tracker_or_create(self) -> BattleStateTracker:
        if self._tracker is None:
            self._tracker = BattleStateTracker()
        return self._tracker

    def reset_tracker(self) -> BattleStateTracker:
        self._tracker = BattleStateTracker()
        self._advisor = None
        if self._hook_registry is not None:
            self._hook_registry.reset()
        return self._tracker

    def get_state(self) -> Dict[str, Any]:
        if self._tracker is None:
            return {}
        return self._tracker.get_state()

    def battle_active(self) -> bool:
        if self._tracker is None:
            return False
        state = self._tracker.get_state()
        return state.get("battle_id") is not None and state.get("result") is None

    # ------------------------------------------------------------------
    # WebSocket client management
    # ------------------------------------------------------------------

    async def add_client(self, ws: WebSocket) -> None:
        await ws.accept()
        self._ws_clients.append(ws)
        if self._tracker is None:
            self._tracker = BattleStateTracker()
        self._ensure_bridge()
        await ws.send_json({"type": "connected", "message": "Battle state tracker ready"})

    def remove_client(self, ws: WebSocket) -> None:
        if ws in self._ws_clients:
            self._ws_clients.remove(ws)

    # ------------------------------------------------------------------
    # Sniffer bridge
    # ------------------------------------------------------------------

    def _ensure_bridge(self) -> None:
        if self._bridge_registered:
            return
        self._bridge_registered = True
        from src.api.sniffer_manager import get_sniffer_manager
        mgr = get_sniffer_manager()
        mgr.register_record_callback(self._on_sniffer_record)

    def _on_sniffer_record(self, record: Dict[str, Any]) -> None:
        if self._tracker is None or not self._ws_clients:
            return
        opcode = record.get("opcode")
        if opcode is None:
            return
        if opcode not in self._LIFECYCLE_OPCODES and opcode not in self._IN_BATTLE_OPCODES:
            return
        if opcode not in self._LIFECYCLE_OPCODES and not self.battle_active():
            return
        _summary = record.get("_summary", {})
        detail = _summary.get("detail", _summary)
        if not isinstance(detail, dict):
            detail = {}
        asyncio.create_task(self.process_event(opcode, detail))

    # ------------------------------------------------------------------
    # Core processing — shared by live sniffer callback and replay
    # ------------------------------------------------------------------

    async def process_event(self, opcode: int, detail: Dict[str, Any]) -> Dict[str, Any]:
        tracker = self.tracker_or_create
        state = tracker.handle_event(opcode, detail)
        round_num = state.get("round", 0)

        formatted = format_battle_event(opcode, detail, state, round_num)
        if formatted:
            await self._push_events(formatted)

        await self._push_state(state)

        if opcode == 0x132C:
            summary = compute_battle_summary(state)
            await self._push_summary(summary)

        # 伤害预测分析
        if self.battle_active() and opcode in (0x1316, 0x131A, 0x1324, 0x13F4):
            await self._push_damage_analysis(state)

        # 钩子分析系统
        if self.battle_active():
            await self._run_analysis_hooks(opcode, detail, state)

        return state

    # ------------------------------------------------------------------
    # WebSocket push helpers
    # ------------------------------------------------------------------

    async def _push_state(self, state: Dict[str, Any]) -> None:
        text = json.dumps({"type": "state_update", "state": state}, ensure_ascii=False)
        dead: List[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.remove(ws)

        if self._tracker is None:
            return
        suggestions = self._tracker.get_suggestions()
        if suggestions:
            sug_text = json.dumps({"type": "suggestions", "suggestions": suggestions}, ensure_ascii=False)
            for ws in self._ws_clients:
                try:
                    await ws.send_text(sug_text)
                except Exception:
                    pass

    async def _push_events(self, events: list) -> None:
        if len(events) == 1:
            msg = json.dumps(
                {"type": "battle_event", "event": events[0].to_dict()},
                ensure_ascii=False,
            )
        else:
            msg = json.dumps(
                {"type": "battle_events", "events": [e.to_dict() for e in events]},
                ensure_ascii=False,
            )
        dead: List[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.remove(ws)

    async def _push_summary(self, summary: Dict[str, Any]) -> None:
        msg = json.dumps({"type": "battle_summary", "summary": summary}, ensure_ascii=False)
        dead: List[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.remove(ws)

    async def _push_damage_analysis(self, state: Dict[str, Any]) -> None:
        from src.analysis.battle_advisor import BattleAdvisor
        if self._advisor is None:
            self._advisor = BattleAdvisor()
        advice = self._advisor.analyze(state)
        if not advice.skill_analysis:
            return
        opp_active = state.get("opp_active")
        opp_traits = BattleAdvisor._extract_traits(opp_active) if opp_active else []
        msg = json.dumps(
            {
                "type": "skill_analysis",
                "skills": [s.to_dict() for s in advice.skill_analysis],
                "traits": advice.traits,
                "opp_traits": opp_traits,
            },
            ensure_ascii=False,
        )
        dead: List[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.remove(ws)

    # ------------------------------------------------------------------
    # Analysis hook dispatch
    # ------------------------------------------------------------------

    def _get_hook_registry(self):
        if self._hook_registry is None:
            from src.analysis.hook_registry import HookRegistry
            from src.analysis.hooks import create_default_hooks
            self._hook_registry = HookRegistry()
            for hook in create_default_hooks():
                self._hook_registry.register(hook)
        return self._hook_registry

    async def _run_analysis_hooks(
        self, opcode: int, detail: Dict[str, Any], state: Dict[str, Any],
    ) -> None:
        from src.analysis.hook_registry import HookTrigger, HookContext

        registry = self._get_hook_registry()
        ctx = HookContext(
            opcode=opcode,
            detail=detail,
            state=state,
            round_num=state.get("round", 0),
            entries=detail.get("entries", []),
        )

        if opcode == 0x1316:
            registry.notify_battle_enter(ctx)

        triggers = self._opcode_to_triggers(opcode, detail)
        all_advice = []
        for trigger in triggers:
            all_advice.extend(registry.dispatch(trigger, ctx))

        if opcode == 0x132C:
            registry.notify_battle_finish(ctx)

        if all_advice:
            await self._push_hook_advice(all_advice)

    # opcode → HookTrigger 映射。
    # 对于 0x1324 (action_resolve)，额外检查 entries 中的 kind
    # 以触发 ON_CHANGE_PET 和 ON_DEFEAT 细粒度事件。
    @staticmethod
    def _opcode_to_triggers(opcode: int, detail: Dict[str, Any]) -> list:
        from src.analysis.hook_registry import HookTrigger

        mapping = {
            0x1316: [HookTrigger.ON_BATTLE_ENTER],
            0x131A: [HookTrigger.ON_ROUND_START],
            0x1324: [HookTrigger.ON_ACTION_RESOLVE],
            0x13F4: [HookTrigger.ON_SPECIAL_REFRESH],
            0x132C: [HookTrigger.ON_BATTLE_FINISH],
        }
        triggers = list(mapping.get(opcode, []))
        if opcode == 0x1324:
            for entry in detail.get("entries", []):
                kind = entry.get("kind")
                if kind == "change_pet":
                    triggers.append(HookTrigger.ON_CHANGE_PET)
                elif kind == "defeat":
                    triggers.append(HookTrigger.ON_DEFEAT)
        return triggers

    async def _push_hook_advice(self, advice_list: list) -> None:
        msg = json.dumps(
            {
                "type": "hook_advice",
                "advice": [a.to_dict() for a in advice_list],
            },
            ensure_ascii=False,
        )
        dead: List[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.remove(ws)

    # ------------------------------------------------------------------
    # WebSocket message handler
    # ------------------------------------------------------------------

    async def handle_message(self, ws: WebSocket, data: Dict[str, Any]) -> None:
        if self._tracker is None:
            await ws.send_json({"type": "error", "message": "No active tracker"})
            return

        msg_type = data.get("type")

        if msg_type == "event":
            opcode = data.get("opcode")
            detail = data.get("detail", {})
            if opcode is not None:
                state = self._tracker.handle_event(opcode, detail)
                await ws.send_json({"type": "state_update", "state": state})
                suggestions = self._tracker.get_suggestions()
                if suggestions:
                    await ws.send_json({"type": "suggestions", "suggestions": suggestions})

        elif msg_type == "get_state":
            state = self._tracker.get_state()
            await ws.send_json({"type": "state", "state": state})

        elif msg_type == "reset":
            self._tracker = BattleStateTracker()
            await ws.send_json({"type": "reset", "message": "Tracker reset"})

        elif msg_type == "request_counter_pick":
            state = self._tracker.get_state()
            opp_active = state.get("opp_active")
            if opp_active:
                await ws.send_json({
                    "type": "counter_pick",
                    "opponent": opp_active,
                    "message": "Consider switching to counter opponent",
                })

        else:
            await ws.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})


# Global singleton
_manager = BattleManager()


def get_battle_manager() -> BattleManager:
    return _manager
