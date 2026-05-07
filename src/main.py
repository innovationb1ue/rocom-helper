"""Roco PvP Helper 应用入口。"""
from __future__ import annotations

import uvicorn


def main():
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
