"""Roco PvP Helper 应用入口。"""
from __future__ import annotations

import uvicorn

from src.utils.logging_config import setup_logging


def main():
    setup_logging()
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
