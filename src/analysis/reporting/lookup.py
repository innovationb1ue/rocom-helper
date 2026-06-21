"""报告 id 和战斗窗口解析。"""
from __future__ import annotations

from pathlib import Path

from src.analysis.reporting.config import DEFAULT_PACKET_ROOT
from src.analysis.reporting.models import BattleBoundary, BattleReportError
from src.analysis.reporting.window import scan_battles


def report_id(session_id: str, battle_index: int) -> str:
    return f"{session_id}:{battle_index}"


def parse_report_id(value: str) -> tuple[str, int]:
    if ":" not in value:
        raise BattleReportError("Invalid report id")
    session_id, battle_index_text = value.rsplit(":", 1)
    if not session_id:
        raise BattleReportError("Invalid report id")
    try:
        battle_index = int(battle_index_text)
    except ValueError as exc:
        raise BattleReportError("Invalid report id") from exc
    if battle_index < 1:
        raise BattleReportError("Invalid report id")
    return session_id, battle_index


def resolve_report(
    report_id_value: str,
    packet_root: Path = DEFAULT_PACKET_ROOT,
) -> tuple[Path, BattleBoundary]:
    session_id, battle_index = parse_report_id(report_id_value)
    session_dir = (packet_root / session_id).resolve()
    packet_root_resolved = packet_root.resolve()
    try:
        session_dir.relative_to(packet_root_resolved)
    except ValueError as exc:
        raise BattleReportError("Session path is outside packet root") from exc
    if not session_dir.is_dir():
        raise BattleReportError("Session not found")

    for boundary in scan_battles(session_dir):
        if boundary.index == battle_index:
            return session_dir, boundary
    raise BattleReportError("Battle not found")

