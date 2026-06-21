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
import uuid
from typing import Any, Dict, Optional

from fastapi import WebSocket

from src.analysis.battle_processor import BattleProcessor
from src.analysis.constants import (
    AUX_BATTLE_OPCODES,
    IN_BATTLE_OPCODES,
    LIFECYCLE_OPCODES,
)
from src.analysis.battle_state import BattleStateTracker
from src.analysis.models import ProcessResult
from src.analysis.replay_messages import build_battle_frame
from src.api.battle_archive import schedule_completed_battle_archive
from src.api.battle_sniffer_bridge import BattleSnifferBridge
from src.api.battle_ws_commands import handle_battle_ws_command
from src.api.ws_hub import JsonWebSocketHub


class BattleManager:
    """管理 WebSocket 连接和事件推送，核心计算委托给 BattleProcessor。"""

    _LIFECYCLE_OPCODES = LIFECYCLE_OPCODES
    _IN_BATTLE_OPCODES = IN_BATTLE_OPCODES
    _AUX_BATTLE_OPCODES = AUX_BATTLE_OPCODES

    def __init__(self) -> None:
        self._processor = BattleProcessor()
        self._ws_hub = JsonWebSocketHub()
        self._sniffer_bridge = BattleSnifferBridge(
            has_clients=self._ws_hub.has_clients,
            battle_active=self.battle_active,
            process_event=self.process_event,
        )
        self._process_lock = asyncio.Lock()
        self._stream_id = self._new_stream_id()
        self._seq = 0
        self._event_index = 0

    @property
    def tracker(self) -> Optional[BattleStateTracker]:
        return self._processor.tracker

    @property
    def tracker_or_create(self) -> BattleStateTracker:
        return self._processor.tracker

    def reset_tracker(self) -> BattleStateTracker:
        self._processor.reset()
        self._reset_stream()
        return self._processor.tracker

    def get_state(self) -> Dict[str, Any]:
        return self._processor.get_state()

    def battle_active(self) -> bool:
        return self._processor.battle_active()

    # ------------------------------------------------------------------
    # WebSocket client management
    # ------------------------------------------------------------------

    async def add_client(self, ws: WebSocket) -> None:
        await self._ws_hub.accept(ws)
        self._ensure_bridge()
        await self._ws_hub.send_json(ws, {"type": "connected", "message": "Battle state tracker ready"})

    def remove_client(self, ws: WebSocket) -> None:
        self._ws_hub.remove(ws)

    # ------------------------------------------------------------------
    # Sniffer bridge
    # ------------------------------------------------------------------

    def _ensure_bridge(self) -> None:
        self._sniffer_bridge.ensure_registered()

    # ------------------------------------------------------------------
    # Core processing — delegates to BattleProcessor, then pushes WebSocket
    # ------------------------------------------------------------------

    async def process_event(
        self,
        opcode: int,
        detail: Dict[str, Any],
        *,
        enable_archive: bool = True,
    ) -> ProcessResult:
        async with self._process_lock:
            result = self._processor.process_event(opcode, detail)
            frame = build_battle_frame(
                opcode,
                result,
                stream_id=self._stream_id,
                seq=self._next_seq(),
                event_index=self._next_event_index(),
            )
            await self._push_message(frame)

            schedule_completed_battle_archive(opcode, enable_archive=enable_archive)

            return result

    async def begin_replay_stream(self) -> BattleStateTracker:
        """Reset state and notify clients that an ordered replay stream starts."""
        tracker = self.reset_tracker()
        await self._push_message({
            "type": "replay_begin",
            "stream_id": self._stream_id,
            "seq": self._seq,
        })
        return tracker

    async def complete_replay_stream(
        self,
        *,
        final_state: Dict[str, Any],
        processed: int,
        total_formatted_events: int,
        stopped_early: bool,
        suggestions: list[Dict[str, str]] | None = None,
    ) -> None:
        await self._push_message({
            "type": "replay_complete",
            "stream_id": self._stream_id,
            "seq": self._next_seq(),
            "state": final_state,
            "result": final_state.get("result"),
            "rounds": final_state.get("round"),
            "processed": processed,
            "total_formatted_events": total_formatted_events,
            "stopped_early": stopped_early,
            "suggestions": suggestions or [],
        })

    # ------------------------------------------------------------------
    # WebSocket push helpers
    # ------------------------------------------------------------------

    async def _push_message(self, message: Dict[str, Any]) -> None:
        await self._ws_hub.broadcast(message)

    @staticmethod
    def _new_stream_id() -> str:
        return uuid.uuid4().hex

    def _reset_stream(self) -> None:
        self._stream_id = self._new_stream_id()
        self._seq = 0
        self._event_index = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _next_event_index(self) -> int:
        self._event_index += 1
        return self._event_index

    # ------------------------------------------------------------------
    # WebSocket message handler
    # ------------------------------------------------------------------

    async def handle_message(self, ws: WebSocket, data: Dict[str, Any]) -> None:
        await handle_battle_ws_command(
            ws,
            self._processor,
            data,
            stream_id=self._stream_id,
            next_seq=self._next_seq,
        )


# Global singleton
_manager = BattleManager()


def get_battle_manager() -> BattleManager:
    return _manager
