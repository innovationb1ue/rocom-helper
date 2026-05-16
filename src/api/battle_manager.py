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

logger = logging.getLogger(__name__)


class BattleManager:
    """管理 WebSocket 连接和事件推送，核心计算委托给 BattleProcessor。"""

    _LIFECYCLE_OPCODES = LIFECYCLE_OPCODES
    _IN_BATTLE_OPCODES = IN_BATTLE_OPCODES

    def __init__(self) -> None:
        self._processor = BattleProcessor()
        self._ws_clients: List[WebSocket] = []
        self._bridge_registered = False

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
        self.ensure_bridge()
        await ws.send_json({"type": "connected", "message": "Battle state tracker ready"})
        logger.info("battle WS client connected, total=%d", len(self._ws_clients))

    def remove_client(self, ws: WebSocket) -> None:
        if ws in self._ws_clients:
            self._ws_clients.remove(ws)
            logger.debug("battle WS client removed, total=%d", len(self._ws_clients))

    # ------------------------------------------------------------------
    # Sniffer bridge
    # ------------------------------------------------------------------

    def ensure_bridge(self) -> None:
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
        result = self._processor.process_event(opcode, detail)

        if result.formatted_events:
            await self._push_events(result.formatted_events)

        await self._push_state(result.state, result.suggestions)

        if opcode == OPCODE_BATTLE_FINISH:
            summary = compute_battle_summary(result.state)
            await self._push_summary(summary)

        if result.battle_advice:
            await self._push_damage_analysis_dict(result.battle_advice, result.state)

        if result.hook_advice:
            await self._push_hook_advice_dicts(result.hook_advice)

        return result

    # ------------------------------------------------------------------
    # WebSocket push helpers
    # ------------------------------------------------------------------

    async def _push_state(
        self, state: Dict[str, Any], suggestions: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        text = json.dumps({"type": "state_update", "state": state}, ensure_ascii=False)
        dead: List[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_text(text)
            except Exception:
                logger.debug("push_state send failed, removing client")
                dead.append(ws)
        for ws in dead:
            self._ws_clients.remove(ws)

        if suggestions:
            sug_text = json.dumps({"type": "suggestions", "suggestions": suggestions}, ensure_ascii=False)
            for ws in self._ws_clients:
                try:
                    await ws.send_text(sug_text)
                except Exception:
                    logger.debug("push suggestions send failed")

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
                logger.debug("push_events send failed, removing client")
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
                logger.debug("push_summary send failed, removing client")
                dead.append(ws)
        for ws in dead:
            self._ws_clients.remove(ws)

    async def _push_damage_analysis_dict(
        self, advice_dict: Dict[str, Any], state: Dict[str, Any],
    ) -> None:
        msg = json.dumps(
            {
                "type": "skill_analysis",
                "skills": advice_dict.get("skill_analysis", []),
                "traits": advice_dict.get("traits", []),
                "opp_traits": advice_dict.get("opp_traits", []),
                "opp_skill_analysis": advice_dict.get("opp_skill_analysis", []),
                "opp_skill_source": advice_dict.get("opp_skill_source", ""),
            },
            ensure_ascii=False,
        )
        dead: List[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_text(msg)
            except Exception:
                logger.debug("push_damage_analysis send failed, removing client")
                dead.append(ws)
        for ws in dead:
            self._ws_clients.remove(ws)

    async def _push_hook_advice_dicts(self, advice_list: List[Dict[str, Any]]) -> None:
        msg = json.dumps(
            {"type": "hook_advice", "advice": advice_list},
            ensure_ascii=False,
        )
        dead: List[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_text(msg)
            except Exception:
                logger.debug("push_hook_advice send failed, removing client")
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
