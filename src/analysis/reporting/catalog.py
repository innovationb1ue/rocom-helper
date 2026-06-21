"""战斗报告目录、summary 和 diagnostics。"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from src.analysis.constants import OPCODE_BATTLE_ENTER, OPCODE_BATTLE_FINISH
from src.analysis.reporting.analysis import build_report_analysis
from src.analysis.reporting.config import DEFAULT_ARCHIVE_ROOT, DEFAULT_PACKET_ROOT
from src.analysis.reporting.lookup import report_id, resolve_report
from src.analysis.reporting.models import (
    BattleBoundary,
    BattleReportDiagnostics,
    BattleReportSummary,
)
from src.analysis.reporting.package import find_archived_report
from src.analysis.reporting.packet_io import DATA_CMD_PATTERN, parse_opcode_hex, read_metadata
from src.analysis.reporting.window import (
    DEFAULT_PAD_AFTER,
    DEFAULT_PAD_BEFORE,
    count_battle_packet_files,
    load_battle_packets_for_window,
    scan_battles,
    select_packet_files,
)


def scan_report_summaries(
    packet_root: Path = DEFAULT_PACKET_ROOT,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
    *,
    pad_before: float = DEFAULT_PAD_BEFORE,
    pad_after: float = DEFAULT_PAD_AFTER,
) -> List[BattleReportSummary]:
    """Scan captured packet sessions and return one item per detected battle."""
    if not packet_root.exists():
        return []

    summaries: List[BattleReportSummary] = []
    for session_dir in sorted(packet_root.glob("*_monitor"), key=lambda p: p.name, reverse=True):
        if not session_dir.is_dir():
            continue
        for boundary in scan_battles(session_dir):
            summaries.append(
                build_report_summary(
                    session_dir,
                    boundary,
                    pad_before=pad_before,
                    pad_after=pad_after,
                    archive_root=archive_root,
                )
            )
    return summaries


def build_report_diagnostics(
    packet_root: Path = DEFAULT_PACKET_ROOT,
    *,
    reports: Optional[List[BattleReportSummary]] = None,
) -> BattleReportDiagnostics:
    """Summarize why battle reports are or are not available."""
    if reports is None:
        reports = scan_report_summaries(packet_root)

    if not packet_root.exists():
        return BattleReportDiagnostics(
            report_count=len(reports),
            packet_session_count=0,
            packet_file_count=0,
            latest_session_id=None,
            latest_session_path=None,
            latest_session_file_count=0,
            battle_enter_count=0,
            battle_finish_count=0,
            completed_battle_count=0,
            incomplete_battle_count=0,
            has_battle_enter=False,
            has_battle_finish=False,
        )

    session_dirs = sorted(
        (p for p in packet_root.glob("*_monitor") if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )
    latest = session_dirs[0] if session_dirs else None
    packet_file_count = 0
    latest_session_file_count = 0
    battle_enter_count = 0
    battle_finish_count = 0
    completed_battle_count = 0
    incomplete_battle_count = 0

    for session_dir in session_dirs:
        files = list(session_dir.glob("*.bin"))
        packet_file_count += len(files)
        if latest is not None and session_dir == latest:
            latest_session_file_count = len(files)

        for fpath in session_dir.glob(DATA_CMD_PATTERN):
            meta = read_metadata(fpath) or {}
            opcode = parse_opcode_hex(meta)
            if opcode == OPCODE_BATTLE_ENTER:
                battle_enter_count += 1
            elif opcode == OPCODE_BATTLE_FINISH:
                battle_finish_count += 1

        for boundary in scan_battles(session_dir):
            if boundary.incomplete:
                incomplete_battle_count += 1
            else:
                completed_battle_count += 1

    return BattleReportDiagnostics(
        report_count=len(reports),
        packet_session_count=len(session_dirs),
        packet_file_count=packet_file_count,
        latest_session_id=latest.name if latest is not None else None,
        latest_session_path=str(latest) if latest is not None else None,
        latest_session_file_count=latest_session_file_count,
        battle_enter_count=battle_enter_count,
        battle_finish_count=battle_finish_count,
        completed_battle_count=completed_battle_count,
        incomplete_battle_count=incomplete_battle_count,
        has_battle_enter=battle_enter_count > 0,
        has_battle_finish=battle_finish_count > 0,
    )


def get_report_summary(
    report_id_value: str,
    packet_root: Path = DEFAULT_PACKET_ROOT,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
    *,
    pad_before: float = DEFAULT_PAD_BEFORE,
    pad_after: float = DEFAULT_PAD_AFTER,
) -> BattleReportSummary:
    session_dir, boundary = resolve_report(report_id_value, packet_root)
    return build_report_summary(
        session_dir,
        boundary,
        pad_before=pad_before,
        pad_after=pad_after,
        include_analysis=True,
        archive_root=archive_root,
    )


def build_report_summary(
    session_dir: Path,
    boundary: BattleBoundary,
    *,
    pad_before: float = DEFAULT_PAD_BEFORE,
    pad_after: float = DEFAULT_PAD_AFTER,
    include_analysis: bool = False,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
) -> BattleReportSummary:
    selected_files = select_packet_files(session_dir, boundary, pad_before=pad_before, pad_after=pad_after)
    battle_packet_count = count_battle_packet_files(selected_files)

    rounds: Optional[int] = None
    result_value: Optional[str] = None
    if include_analysis:
        packets = load_battle_packets_for_window(session_dir, boundary, pad_before=pad_before, pad_after=pad_after)
        analysis = build_report_analysis(packets, include_events=False)
        final_state = analysis.get("final_state", {})
        rounds = final_state.get("round")
        result_value = final_state.get("result")
        battle_packet_count = len(packets)

    session_id = session_dir.name
    rid = report_id(session_id, boundary.index)
    archived_path = find_archived_report(rid, archive_root=archive_root)
    return BattleReportSummary(
        report_id=rid,
        session_id=session_id,
        battle_index=boundary.index,
        enter_ts=boundary.enter_ts,
        finish_ts=boundary.finish_ts,
        duration_seconds=round(boundary.duration, 3),
        complete=not boundary.incomplete,
        file_count=len(selected_files),
        battle_packet_count=battle_packet_count,
        rounds=rounds,
        result=result_value,
        session_path=str(session_dir),
        archived=archived_path is not None,
        archive_path=str(archived_path) if archived_path else None,
    )

