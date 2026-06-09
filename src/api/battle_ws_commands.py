"""`/ws/battle` 客户端命令处理。

这里仅处理 WebSocket 上行控制消息；实时抓包和回放推送仍走 BattleManager.process_event。
"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.battle_processor import BattleProcessor


async def handle_battle_ws_command(ws: Any, processor: BattleProcessor, data: Dict[str, Any]) -> None:
    """处理 battle WebSocket 收到的单条客户端命令。"""
    msg_type = data.get("type")

    if msg_type == "event":
        opcode = data.get("opcode")
        detail = data.get("detail", {})
        if opcode is not None:
            result = processor.process_event(opcode, detail if isinstance(detail, dict) else {})
            await ws.send_json({"type": "state_update", "state": result.state})
            if result.suggestions:
                await ws.send_json({"type": "suggestions", "suggestions": result.suggestions})
        return

    if msg_type == "get_state":
        await ws.send_json({"type": "state", "state": processor.get_state()})
        return

    if msg_type == "reset":
        processor.reset()
        await ws.send_json({"type": "reset", "message": "Tracker reset"})
        return

    if msg_type == "request_counter_pick":
        state = processor.get_state()
        opp_active = state.get("opp_active")
        if opp_active:
            await ws.send_json({
                "type": "counter_pick",
                "opponent": opp_active,
                "message": "Consider switching to counter opponent",
            })
        return

    await ws.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})
