"""集中式日志配置 — 带轮转和分级输出。

用法::

    from src.utils.logging_config import setup_logging
    setup_logging()          # INFO 控制台, DEBUG 文件

日志文件:
  logs/app.log      DEBUG 级别, 10MB × 5 份轮转
  logs/error.log    ERROR 级别, 5MB × 3 份轮转
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LOG_DIR = _PROJECT_ROOT / "logs"

_FMT = logging.Formatter(
    "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def setup_logging(level: str | int = logging.INFO) -> None:
    """配置根 logger，在整个应用中只需调用一次。

    Parameters
    ----------
    level:
        控制台输出的最低级别。默认 INFO。
        文件始终记录 DEBUG 及以上。
    """
    root = logging.getLogger()

    # 幂等：已配置则跳过
    if root.handlers:
        return

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root.setLevel(logging.DEBUG)

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 控制台 — 只显示 level 及以上
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(_FMT)
    root.addHandler(console)

    # app.log — 全量 DEBUG
    app_fh = RotatingFileHandler(
        _LOG_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    app_fh.setLevel(logging.DEBUG)
    app_fh.setFormatter(_FMT)
    root.addHandler(app_fh)

    # error.log — 仅 ERROR，便于快速排查
    err_fh = RotatingFileHandler(
        _LOG_DIR / "error.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    err_fh.setLevel(logging.ERROR)
    err_fh.setFormatter(_FMT)
    root.addHandler(err_fh)


def hex_preview(data: bytes, max_len: int = 64) -> str:
    """将字节格式化为十六进制预览，用于日志输出。"""
    if len(data) <= max_len:
        return data.hex()
    return data[:max_len].hex() + f"... ({len(data)}B total)"
