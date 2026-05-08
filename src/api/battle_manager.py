"""全局战斗状态管理器 — 单例，可从任何模块访问。"""
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
