"""实时战斗 WebSocket 路由。"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.analysis.battle_state import BattleStateTracker

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        self.tracker: Optional[BattleStateTracker] = None
        self._bridge_registered = False

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        if self.tracker is None:
            self.tracker = BattleStateTracker()
        self._ensure_bridge()
        await ws.send_json({"type": "connected", "message": "Battle state tracker ready"})

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    def _ensure_bridge(self):
        """注册 Sniffer → Battle 的记录桥接（只注册一次）。"""
        if self._bridge_registered:
            return
        self._bridge_registered = True
        from src.api.sniffer_manager import get_sniffer_manager
        mgr = get_sniffer_manager()
        mgr.register_record_callback(self._on_sniffer_record)

    # 战斗生命周期 opcodes：始终处理
    _LIFECYCLE_OPCODES = {0x1316, 0x131A, 0x132C, 0x0102}
    # 战斗内 opcodes：仅在战斗激活后才处理
    _IN_BATTLE_OPCODES = {
        0x130B, 0x1322, 0x1324, 0x13F4, 0x130C,
        0x01A9, 0x0220, 0x13FC, 0x13F3, 0x1312,
        0x1326, 0x132A, 0x132D, 0x1334, 0x133C, 0x13F6,
    }

    def _battle_active(self) -> bool:
        """判断是否处于战斗中。"""
        if self.tracker is None:
            return False
        state = self.tracker.get_state()
        return state.get("battle_id") is not None and state.get("result") is None

    def _on_sniffer_record(self, record: Dict[str, Any]) -> None:
        """由 SnifferManager 通过 call_soon_threadsafe 在事件循环中调用。"""
        if self.tracker is None or not self.active:
            return
        opcode = record.get("opcode")
        if opcode is None:
            return
        if opcode not in self._LIFECYCLE_OPCODES and opcode not in self._IN_BATTLE_OPCODES:
            return
        # 非生命周期 opcode 只在战斗中处理
        if opcode not in self._LIFECYCLE_OPCODES and not self._battle_active():
            return
        detail = record.get("_summary", {})
        if not isinstance(detail, dict):
            detail = {}
        try:
            state = self.tracker.handle_event(opcode, detail)
            asyncio.create_task(self._push_state(state))
        except Exception as exc:
            logger.warning("处理战斗记录失败: %s", exc)

    async def _push_state(self, state: Dict[str, Any]) -> None:
        """推送状态更新到所有已连接的 Battle WebSocket 客户端。"""
        text = json.dumps({"type": "state_update", "state": state}, ensure_ascii=False)
        dead: List[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)

        if self.tracker is None:
            return
        suggestions = self.tracker.get_suggestions()
        if suggestions:
            sug_text = json.dumps({"type": "suggestions", "suggestions": suggestions}, ensure_ascii=False)
            for ws in self.active:
                try:
                    await ws.send_text(sug_text)
                except Exception:
                    pass

    async def handle_message(self, ws: WebSocket, data: Dict[str, Any]):
        if self.tracker is None:
            await ws.send_json({"type": "error", "message": "No active tracker"})
            return

        msg_type = data.get("type")

        if msg_type == "event":
            opcode = data.get("opcode")
            detail = data.get("detail", {})
            if opcode is not None:
                state = self.tracker.handle_event(opcode, detail)
                await ws.send_json({"type": "state_update", "state": state})
                suggestions = self.tracker.get_suggestions()
                if suggestions:
                    await ws.send_json({"type": "suggestions", "suggestions": suggestions})

        elif msg_type == "get_state":
            state = self.tracker.get_state()
            await ws.send_json({"type": "state", "state": state})

        elif msg_type == "reset":
            self.tracker = BattleStateTracker()
            await ws.send_json({"type": "reset", "message": "Tracker reset"})

        elif msg_type == "request_counter_pick":
            state = self.tracker.get_state()
            opp_active = state.get("opp_active")
            if opp_active:
                await ws.send_json({
                    "type": "counter_pick",
                    "opponent": opp_active,
                    "message": "Consider switching to counter opponent",
                })

        else:
            await ws.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})


_manager = ConnectionManager()


@router.websocket("/ws/battle")
async def battle_websocket(ws: WebSocket):
    await _manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue
            await _manager.handle_message(ws, data)
    except WebSocketDisconnect:
        _manager.disconnect(ws)
        logger.info("Battle WebSocket disconnected")
