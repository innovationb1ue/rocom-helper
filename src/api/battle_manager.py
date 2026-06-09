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
from src.analysis.replay_messages import build_battle_messages
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
            for message in build_battle_messages(opcode, result):
                await self._push_message(message)

            schedule_completed_battle_archive(opcode, enable_archive=enable_archive)

            return result

    # ------------------------------------------------------------------
    # WebSocket push helpers
    # ------------------------------------------------------------------

    async def _push_message(self, message: Dict[str, Any]) -> None:
        await self._ws_hub.broadcast(message)

    # ------------------------------------------------------------------
    # WebSocket message handler
    # ------------------------------------------------------------------

    async def handle_message(self, ws: WebSocket, data: Dict[str, Any]) -> None:
        await handle_battle_ws_command(ws, self._processor, data)


# Global singleton
_manager = BattleManager()


def get_battle_manager() -> BattleManager:
    return _manager
