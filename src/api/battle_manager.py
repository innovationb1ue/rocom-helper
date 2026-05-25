"""全局战斗状态管理器 — 单例模式，桥接嗅探器与 WebSocket 客户端。

BattleManager 负责网络层的编排：
  - 管理 WebSocket 客户端连接列表
  - 注册嗅探器回调，实时处理战斗数据包
  - 将 BattleProcessor 的计算结果推送至 WebSocket 客户端

核心计算逻辑委托给 BattleProcessor（不依赖 FastAPI/WebSocket）。
通过 get_battle_manager() 全局访问（单例模式）。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from src.analysis.battle_processor import BattleProcessor, ProcessResult, compute_battle_summary
from src.analysis.constants import (
    IN_BATTLE_OPCODES,
    LIFECYCLE_OPCODES,
    OPCODE_BATTLE_FINISH,
)
from src.analysis.battle_state import BattleStateTracker
from src.analysis.replay_messages import build_battle_messages

logger = logging.getLogger(__name__)


class BattleManager:
    """管理 WebSocket 连接和事件推送，核心计算委托给 BattleProcessor。"""

    _LIFECYCLE_OPCODES = LIFECYCLE_OPCODES
    _IN_BATTLE_OPCODES = IN_BATTLE_OPCODES

    def __init__(self) -> None:
        self._processor = BattleProcessor()
        self._ws_clients: List[WebSocket] = []
        self._bridge_registered = False
        self._process_lock = asyncio.Lock()

    @property
    def tracker(self) -> Optional[BattleStateTracker]:
        return self._processor.tracker

    @property
    def tracker_or_create(self) -> BattleStateTracker:
        return self._processor.tracker

    def reset_tracker(self) -> BattleStateTracker:
        self._processor.reset()
        return self._processor.tracker

    def get_state(self) -> Dict[str, Any]:
        return self._processor.get_state()

    def battle_active(self) -> bool:
        return self._processor.battle_active()

    # ------------------------------------------------------------------
    # WebSocket client management
    # ------------------------------------------------------------------

    async def add_client(self, ws: WebSocket) -> None:
        await ws.accept()
        self._ws_clients.append(ws)
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
        if not self._ws_clients:
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
    # Core processing — delegates to BattleProcessor, then pushes WebSocket
    # ------------------------------------------------------------------

    async def process_event(self, opcode: int, detail: Dict[str, Any]) -> ProcessResult:
        async with self._process_lock:
            result = self._processor.process_event(opcode, detail)
            for message in build_battle_messages(opcode, result):
                await self._push_message(message)

            return result

    # ------------------------------------------------------------------
    # WebSocket push helpers
    # ------------------------------------------------------------------

    async def _push_message(self, message: Dict[str, Any]) -> None:
        text = json.dumps(message, ensure_ascii=False)
        dead: List[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.remove(ws)

    # ------------------------------------------------------------------
    # WebSocket message handler
    # ------------------------------------------------------------------

    async def handle_message(self, ws: WebSocket, data: Dict[str, Any]) -> None:
        if self._processor.tracker is None:
            await ws.send_json({"type": "error", "message": "No active tracker"})
            return

        msg_type = data.get("type")

        if msg_type == "event":
            opcode = data.get("opcode")
            detail = data.get("detail", {})
            if opcode is not None:
                result = self._processor.process_event(opcode, detail)
                await ws.send_json({"type": "state_update", "state": result.state})
                if result.suggestions:
                    await ws.send_json({"type": "suggestions", "suggestions": result.suggestions})

        elif msg_type == "get_state":
            state = self._processor.get_state()
            await ws.send_json({"type": "state", "state": state})

        elif msg_type == "reset":
            self._processor.reset()
            await ws.send_json({"type": "reset", "message": "Tracker reset"})

        elif msg_type == "request_counter_pick":
            state = self._processor.get_state()
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
