"""实时战斗 WebSocket 路由。"""
from __future__ import annotations

import asyncio
import urllib.parse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from src.analysis.battle_summary import compute_battle_summary
from src.analysis.battle_state import BattleStateTracker
from src.analysis.constants import OPCODE_ROUND_START
from src.analysis.battle_report import (
    BattleReportError,
    get_report_summary,
    get_report_package,
    scan_report_summaries,
)
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


@router.get("/api/battle/reports")
async def list_battle_reports():
    reports = scan_report_summaries()
    return {"reports": [r.__dict__ for r in reports]}


@router.get("/api/battle/reports/{report_id}")
async def get_battle_report(report_id: str):
    try:
        return get_report_summary(urllib.parse.unquote(report_id)).__dict__
    except BattleReportError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/battle/reports/{report_id}/download")
async def download_battle_report(report_id: str):
    try:
        filename, payload = get_report_package(urllib.parse.unquote(report_id))
    except BattleReportError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Filename": filename,
        },
    )


# ------------------------------------------------------------------
# Replay endpoint
# ------------------------------------------------------------------


# 回放端点的处理流程:
# 1. 从 tests/fixtures/packets/{session} 加载预录数据包
# 2. 对每个包: 解析 protobuf → summarize 提取语义 → process_event 推送
# 3. 支持 stop_round 参数，在指定回合后停止
# 4. 每个包之间按 delay_ms 毫秒间隔推送
# 5. 返回处理统计（包数、格式化事件数、结果等）
@router.post("/api/battle/replay")
async def replay_battle_packets(
    delay_ms: int = 80,
    session: str = "battle_session_1",
    stop_round: Optional[int] = None,
):
    """回放 tests/fixtures 中的战斗包到 WebSocket 客户端。

    Args:
        stop_round: 如果指定，回放在此回合结束后停止（不处理下一回合的 round_start）。
    """
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
    stopped_early = False

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

        # 如果指定了 stop_round，在处理 round_start 前检查是否超出目标回合
        if stop_round is not None and opcode == OPCODE_ROUND_START:
            current_round = mgr.get_state().get("round", 0)
            incoming_round = detail.get("round", current_round + 1)
            if incoming_round > stop_round:
                stopped_early = True
                break

        result = await mgr.process_event(opcode, detail, enable_archive=False)
        processed += 1
        total_formatted += len(result.formatted_events)

        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

    final_state = result.state

    return {
        "status": "ok",
        "processed": processed,
        "total_formatted_events": total_formatted,
        "result": final_state.get("result"),
        "rounds": final_state.get("round"),
        "stopped_early": stopped_early,
        "my_pets": len(final_state.get("my_pets", [])),
        "opp_pets": len(final_state.get("opp_pets", [])),
    }
