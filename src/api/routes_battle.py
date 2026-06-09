"""实时战斗 WebSocket 路由。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket

import src.api.battle_report_endpoints as battle_report_endpoints
from src.api.battle_manager import get_battle_manager
from src.api.battle_route_actions import (
    battle_effects_route_payload,
    battle_pets_route_payload,
    battle_state_payload,
    replay_battle_route_payload,
)
from src.api.battle_ws_endpoint import handle_battle_ws_connection

router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ------------------------------------------------------------------
# WebSocket endpoint
# ------------------------------------------------------------------


@router.websocket("/ws/battle")
async def battle_websocket(ws: WebSocket):
    mgr = get_battle_manager()
    await handle_battle_ws_connection(ws, mgr)


# ------------------------------------------------------------------
# REST API endpoints
# ------------------------------------------------------------------


@router.get("/api/battle/state")
async def get_battle_state():
    mgr = get_battle_manager()
    return battle_state_payload(mgr)


@router.get("/api/battle/pets")
async def get_battle_pets():
    mgr = get_battle_manager()
    return battle_pets_route_payload(mgr)


@router.get("/api/battle/effects")
async def get_battle_effects():
    mgr = get_battle_manager()
    return battle_effects_route_payload(mgr)


@router.get("/api/battle/reports")
async def list_battle_reports():
    return battle_report_endpoints.list_battle_reports_payload()


@router.get("/api/battle/reports/{report_id}")
async def get_battle_report(report_id: str):
    return battle_report_endpoints.get_battle_report_payload(report_id)


@router.get("/api/battle/reports/{report_id}/download")
async def download_battle_report(report_id: str):
    return battle_report_endpoints.download_battle_report_response(report_id)


# ------------------------------------------------------------------
# Replay endpoint
# ------------------------------------------------------------------


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
    mgr = get_battle_manager()
    return await replay_battle_route_payload(
        mgr,
        project_root=_PROJECT_ROOT,
        session=session,
        delay_ms=delay_ms,
        stop_round=stop_round,
    )
