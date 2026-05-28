"""抓包连接测试 API — 持久化监听 + WebSocket 实时状态。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from src.api.sniffer_manager import get_sniffer_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/start")
async def start_sniffer():
    """启动持久化 Sniffer 监听。"""
    mgr = get_sniffer_manager()
    if mgr.state in ("listening", "connected", "key_missing", "key_captured"):
        return {"status": "already_running", "message": "已在监听中", "details": mgr.get_status()}
    try:
        await mgr.start()
    except RuntimeError as exc:
        logger.warning("启动 Sniffer 失败: %s", exc)
        raise HTTPException(status_code=503, detail=mgr.state_message) from exc
    except Exception as exc:
        logger.exception("启动 Sniffer 异常")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", "message": "监听已启动", "details": mgr.get_status()}


@router.post("/stop")
async def stop_sniffer():
    """停止 Sniffer 监听。"""
    mgr = get_sniffer_manager()
    await mgr.stop()
    return {"status": "ok", "message": "监听已停止", "details": mgr.get_status()}


@router.get("/status")
async def sniffer_status():
    """获取当前监听状态。"""
    mgr = get_sniffer_manager()
    return {"status": "ok", "details": mgr.get_status()}


@router.websocket("/ws/monitor")
async def sniffer_monitor_ws(ws: WebSocket):
    """WebSocket 实时推送监听状态和包事件。"""
    await ws.accept()
    mgr = get_sniffer_manager()
    mgr.add_client(ws)

    # 立即推送当前状态
    try:
        status = mgr.get_status()
        await ws.send_text(json.dumps({
            "type": "status",
            "status": status["status"],
            "message": status["message"],
            "flow_count": status["flow_count"],
            "key_hex": status["key_hex"],
        }, ensure_ascii=False))
    except Exception:
        mgr.remove_client(ws)
        return

    try:
        while True:
            # 保持连接，等待客户端消息（ping/pong 或控制指令）
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "get_status":
                status = mgr.get_status()
                await ws.send_text(json.dumps({
                    "type": "status",
                    "status": status["status"],
                    "message": status["message"],
                    "flow_count": status["flow_count"],
                    "key_hex": status["key_hex"],
                }, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        mgr.remove_client(ws)
