"""FastAPI 应用工厂 — Roco PvP Helper API。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Roco PvP Helper API starting...")

    # Auto-start sniffer (graceful degradation if Scapy/Npcap unavailable)
    from src.api.sniffer_manager import get_sniffer_manager
    _sniffer_mgr = get_sniffer_manager()
    try:
        await _sniffer_mgr.start()
        logger.info("Sniffer auto-started successfully")
    except Exception as exc:
        logger.warning("Sniffer auto-start failed (non-fatal): %s", exc)

    # Pre-register battle bridge (don't wait for first WS client)
    from src.api.battle_manager import get_battle_manager
    get_battle_manager().ensure_bridge()

    yield

    try:
        await _sniffer_mgr.stop()
    except Exception:
        pass
    logger.info("Roco PvP Helper API shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Roco PvP Helper",
        version="0.1.0",
        description="洛克王国 PvP 辅助工具 API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from src.api.routes_pets import router as pets_router
    from src.api.routes_teams import router as teams_router
    from src.api.routes_battle import router as battle_router
    from src.api.routes_data import router as data_router
    from src.api.routes_sniffer import router as sniffer_router
    from src.api.routes_config import router as config_router

    app.include_router(pets_router, prefix="/api")
    app.include_router(teams_router, prefix="/api/teams")
    app.include_router(battle_router)
    app.include_router(data_router, prefix="/api/data")
    app.include_router(sniffer_router, prefix="/api/sniffer")
    app.include_router(config_router, prefix="/api")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
