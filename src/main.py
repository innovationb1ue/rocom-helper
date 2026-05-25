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
    )


if __name__ == "__main__":
    main()
