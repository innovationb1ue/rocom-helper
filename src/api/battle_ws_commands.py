"""`/ws/battle` 客户端命令处理。

这里仅处理 WebSocket 上行控制消息；实时抓包和回放推送仍走 BattleManager.process_event。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from src.analysis.battle_processor import BattleProcessor


NextSeq = Callable[[], int]


async def handle_battle_ws_command(
    ws: Any,
    processor: BattleProcessor,
    data: Dict[str, Any],
    *,
    stream_id: Optional[str] = None,
    next_seq: Optional[NextSeq] = None,
) -> None:
    """处理 battle WebSocket 收到的单条客户端命令。"""
    msg_type = data.get("type")

    if msg_type == "event":
        opcode = data.get("opcode")
        detail = data.get("detail", {})
        if opcode is not None:
            result = processor.process_event(opcode, detail if isinstance(detail, dict) else {})
            await ws.send_json(_state_update(result.state, stream_id, next_seq))
            if result.suggestions:
                await ws.send_json({"type": "suggestions", "suggestions": result.suggestions})
        return

    if msg_type == "get_state":
        await ws.send_json(_state_update(processor.get_state(), stream_id, next_seq))
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


def _state_update(
    state: Dict[str, Any],
    stream_id: Optional[str],
    next_seq: Optional[NextSeq],
) -> Dict[str, Any]:
    message: Dict[str, Any] = {"type": "state_update", "state": state}
    if stream_id and next_seq:
        message["stream_id"] = stream_id
        message["seq"] = next_seq()
    return message
