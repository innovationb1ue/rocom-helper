"""Roco PvP Helper 应用入口。"""
from __future__ import annotations

import uvicorn

from src.config import settings


def main():
    uvicorn.run(
        "src.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        # 回放会在同一 WebSocket 上连续推送大量战斗消息；禁用底层
        # keepalive ping，避免 ping 与业务消息竞争写入导致库层异常。
        ws_ping_interval=None,
    )


if __name__ == "__main__":
    main()
