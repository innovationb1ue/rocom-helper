"""实时战斗 WebSocket 路由。"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.analysis.battle_state import BattleStateTracker
from src.analysis.event_formatter import format_battle_event, compute_battle_summary
from src.api.battle_manager import get_battle_manager

logger = logging.getLogger(__name__)

router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ------------------------------------------------------------------
# WebSocket endpoint
# ------------------------------------------------------------------


@router.websocket("/ws/battle")
async def battle_websocket(ws: WebSocket):
    mgr = get_battle_manager()
    await mgr.add_client(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue
            await mgr.handle_message(ws, data)
    except WebSocketDisconnect:
        mgr.remove_client(ws)
        logger.info("Battle WebSocket disconnected")


# ------------------------------------------------------------------
# REST API endpoints
# ------------------------------------------------------------------


@router.get("/api/battle/state")
async def get_battle_state():
    mgr = get_battle_manager()
    return mgr.get_state()


@router.get("/api/battle/pets")
async def get_battle_pets():
    mgr = get_battle_manager()
    state = mgr.get_state()
    return {
        "my_pets": state.get("my_pets", []),
        "opp_pets": state.get("opp_pets", []),
        "my_active": state.get("my_active"),
        "opp_active": state.get("opp_active"),
    }


@router.get("/api/battle/effects")
async def get_battle_effects():
    mgr = get_battle_manager()
    state = mgr.get_state()
    my_buffs = []
    opp_buffs = []
    for pet in state.get("my_pets", []):
        my_buffs.append({"pet_name": pet.get("name"), "buffs": pet.get("buffs", [])})
    for pet in state.get("opp_pets", []):
        opp_buffs.append({"pet_name": pet.get("name"), "buffs": pet.get("buffs", [])})
    return {
        "weather": state.get("weather"),
        "phase": state.get("phase"),
        "my_buffs": my_buffs,
        "opp_buffs": opp_buffs,
    }


# ------------------------------------------------------------------
# Replay endpoint
# ------------------------------------------------------------------


@router.post("/api/battle/replay")
async def replay_battle_packets(
    delay_ms: int = 80,
    session: str = "battle_session_1",
):
    """回放 tests/fixtures 中的战斗包到 WebSocket 客户端。"""
    from src.protocol.proto_core import extract_inner_message
    from src.protocol.opcodes import summarize
    from tests.packet_reader import load_battle_packets

    session_dir = _PROJECT_ROOT / "tests" / "fixtures" / "packets" / session
    if not session_dir.is_dir():
        return {"status": "error", "message": f"Session not found: {session_dir}"}

    packets = load_battle_packets(session_dir)
    if not packets:
        return {"status": "error", "message": "No battle packets found"}

    mgr = get_battle_manager()
    mgr.reset_tracker()

    processed = 0
    total_formatted = 0

    for item in packets:
        record = item["record"]
        opcode = item["opcode"]

        inner = None
        if opcode == 0x0414:
            inner = extract_inner_message(record.get("root", {}))

        _kind, summary = summarize(record, inner)
        detail = summary.get("detail", summary) if isinstance(summary, dict) else {}
        if not isinstance(detail, dict):
            detail = {}

        state = await mgr.process_event(opcode, detail)
        processed += 1

        if state.get("result") is None:
            round_num = state.get("round", 0)
            formatted = format_battle_event(opcode, detail, state, round_num)
            total_formatted += len(formatted)

        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

    final_state = mgr.get_state()

    return {
        "status": "ok",
        "processed": processed,
        "total_formatted_events": total_formatted,
        "result": final_state.get("result"),
        "rounds": final_state.get("round"),
        "my_pets": len(final_state.get("my_pets", [])),
        "opp_pets": len(final_state.get("opp_pets", [])),
    }
