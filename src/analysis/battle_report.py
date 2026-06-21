"""Battle report export helpers.

The report package is intended for support/debugging: it keeps the original
RC01 packet files intact with enough metadata to identify the battle window.

This module is a compatibility facade. Implementation lives in
``src.analysis.reporting`` modules so scanning, package export, compact
analysis and packet I/O can be tested independently.
"""
from __future__ import annotations

from src.analysis.reporting.analysis import build_report_analysis, compact_messages
from src.analysis.reporting.catalog import (
    build_report_diagnostics,
    build_report_summary,
    get_report_summary,
    scan_report_summaries,
)
from src.analysis.reporting.config import (
    DEFAULT_ARCHIVE_ROOT,
    DEFAULT_PACKET_ROOT,
    PROJECT_ROOT,
    REPORT_FORMAT_VERSION,
)
from src.analysis.reporting.lookup import parse_report_id, report_id, resolve_report
from src.analysis.reporting.models import (
    BattleBoundary,
    BattleReportDiagnostics,
    BattleReportError,
    BattleReportSummary,
)
from src.analysis.reporting.package import (
    archive_latest_completed_battle,
    archive_report_package,
    build_manifest,
    build_report_package,
    find_archived_report,
    get_report_package,
    report_archive_path,
    report_filename,
)
from src.analysis.reporting.packet_io import (
    DATA_CMD_PATTERN,
    extract_timestamp as _extract_timestamp,
    parse_opcode_hex,
    read_bin_packet,
    read_metadata,
    ts_to_seconds,
)
from src.analysis.reporting.window import (
    BATTLE_OPCODES,
    DEFAULT_PAD_AFTER,
    DEFAULT_PAD_BEFORE,
    count_battle_packet_files,
    load_battle_packets_for_window,
    scan_battles,
    select_packet_files,
)
