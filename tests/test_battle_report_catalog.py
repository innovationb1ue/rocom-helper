from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from src.analysis.battle_report import scan_report_summaries as facade_scan_report_summaries
from src.analysis.reporting.catalog import (
    build_report_diagnostics,
    get_report_summary,
    scan_report_summaries,
)
from src.analysis.reporting.lookup import parse_report_id, report_id, resolve_report
from src.analysis.reporting.models import BattleReportError

FIXTURE_SESSION = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"


@pytest.fixture()
def packet_root(tmp_path: Path) -> Path:
    if not FIXTURE_SESSION.exists():
        pytest.skip("battle_session_1 fixture not found")
    root = tmp_path / "logs" / "packets"
    shutil.copytree(FIXTURE_SESSION, root / "2026-05-07_21-17-31_monitor")
    return root


def test_lookup_parses_and_resolves_report_id(packet_root: Path):
    rid = report_id("2026-05-07_21-17-31_monitor", 1)

    session_id, battle_index = parse_report_id(rid)
    session_dir, boundary = resolve_report(rid, packet_root)

    assert session_id == "2026-05-07_21-17-31_monitor"
    assert battle_index == 1
    assert session_dir.name == session_id
    assert boundary.index == 1


@pytest.mark.parametrize("value", ["", "session", "session:x", "session:0"])
def test_lookup_rejects_invalid_report_id(value: str):
    with pytest.raises(BattleReportError):
        parse_report_id(value)


def test_catalog_scan_matches_facade_and_marks_archive_state(packet_root: Path, tmp_path: Path):
    archive_root = tmp_path / "archives"

    direct = scan_report_summaries(packet_root, archive_root)
    through_facade = facade_scan_report_summaries(packet_root, archive_root)

    assert direct == through_facade
    assert len(direct) == 1
    assert direct[0].report_id == "2026-05-07_21-17-31_monitor:1"
    assert direct[0].archived is False


def test_catalog_diagnostics_counts_complete_and_missing_roots(packet_root: Path, tmp_path: Path):
    complete = build_report_diagnostics(packet_root)
    missing = build_report_diagnostics(tmp_path / "missing")

    assert complete.report_count == 1
    assert complete.packet_session_count == 1
    assert complete.battle_enter_count == 1
    assert complete.battle_finish_count == 1
    assert complete.completed_battle_count == 1
    assert complete.incomplete_battle_count == 0
    assert missing.report_count == 0
    assert missing.packet_session_count == 0


def test_catalog_summary_can_include_compact_replay_analysis(packet_root: Path):
    summary = get_report_summary("2026-05-07_21-17-31_monitor:1", packet_root)

    assert summary.rounds == 17
    assert summary.result == "WIN_HP"
    assert summary.battle_packet_count == 227
