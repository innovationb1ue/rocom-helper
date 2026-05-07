"""数据管理 API 路由。"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from src.data.loader import get_bundle, invalidate_cache

logger = logging.getLogger(__name__)

router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_MANIFEST_PATH = _PROJECT_ROOT / "data" / "game" / "data_manifest.json"


@router.get("/status")
async def data_status():
    bundle = get_bundle()
    stats = {}
    for key, val in bundle.items():
        if isinstance(val, dict):
            stats[key] = len(val)
        elif isinstance(val, list):
            stats[key] = len(val)

    manifest = {}
    if _MANIFEST_PATH.exists():
        with open(_MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    return {
        "status": "ok",
        "loaded_tables": stats,
        "total_records": sum(stats.values()),
        "manifest": manifest,
    }


@router.post("/refresh")
async def refresh_data():
    invalidate_cache()
    bundle = get_bundle()
    stats = {}
    for key, val in bundle.items():
        if isinstance(val, dict):
            stats[key] = len(val)
    return {"status": "refreshed", "loaded_tables": stats}
