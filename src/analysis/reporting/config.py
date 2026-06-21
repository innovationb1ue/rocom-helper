"""战斗报告路径与格式配置。"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_PACKET_ROOT = PROJECT_ROOT / "logs" / "packets"
DEFAULT_ARCHIVE_ROOT = PROJECT_ROOT / "logs" / "battle_reports"
REPORT_FORMAT_VERSION = 2

