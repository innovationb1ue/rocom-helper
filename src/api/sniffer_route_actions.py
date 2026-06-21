"""Sniffer REST route action helpers."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)

RUNNING_STATES = {"listening", "connected", "key_missing", "key_captured"}


async def start_sniffer_payload(manager: Any) -> dict:
    """Start sniffer manager and preserve the legacy REST response contract."""
    if manager.state in RUNNING_STATES:
        return {
            "status": "already_running",
            "message": "已在监听中",
            "details": manager.get_status(),
        }
    try:
        await manager.start()
    except RuntimeError as exc:
        logger.warning("启动 Sniffer 失败: %s", exc)
        raise HTTPException(status_code=503, detail=manager.state_message) from exc
    except Exception as exc:
        logger.exception("启动 Sniffer 异常")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", "message": "监听已启动", "details": manager.get_status()}


async def stop_sniffer_payload(manager: Any) -> dict:
    await manager.stop()
    return {"status": "ok", "message": "监听已停止", "details": manager.get_status()}


def sniffer_status_payload(manager: Any) -> dict:
    return {"status": "ok", "details": manager.get_status()}
