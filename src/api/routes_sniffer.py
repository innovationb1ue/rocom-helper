"""抓包连接测试 API — 持久化监听 + WebSocket 实时状态。"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket

from src.api.sniffer_manager import get_sniffer_manager
from src.api.sniffer_route_actions import (
    sniffer_status_payload,
    start_sniffer_payload,
    stop_sniffer_payload,
)
from src.api.sniffer_ws_monitor import handle_monitor_connection

router = APIRouter()


@router.post("/start")
async def start_sniffer():
    """启动持久化 Sniffer 监听。"""
    mgr = get_sniffer_manager()
    return await start_sniffer_payload(mgr)


@router.post("/stop")
async def stop_sniffer():
    """停止 Sniffer 监听。"""
    mgr = get_sniffer_manager()
    return await stop_sniffer_payload(mgr)


@router.get("/status")
async def sniffer_status():
    """获取当前监听状态。"""
    mgr = get_sniffer_manager()
    return sniffer_status_payload(mgr)


@router.websocket("/ws/monitor")
async def sniffer_monitor_ws(ws: WebSocket):
    """WebSocket 实时推送监听状态和包事件。"""
    mgr = get_sniffer_manager()
    await handle_monitor_connection(ws, mgr)
