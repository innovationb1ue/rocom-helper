from __future__ import annotations

import json
import shutil
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from src.analysis.battle_report import (
    archive_latest_completed_battle,
    archive_report_package,
    build_report_analysis,
    build_report_package,
    find_archived_report,
    get_report_summary,
    get_report_package,
    load_battle_packets_for_window,
    parse_opcode_hex,
    read_metadata,
    report_id,
    scan_battles,
    scan_report_summaries,
)


FIXTURE_SESSION = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"


@pytest.fixture()
def packet_root(tmp_path: Path) -> Path:
    if not FIXTURE_SESSION.exists():
        pytest.skip("battle_session_1 fixture not found")
    root = tmp_path / "logs" / "packets"
    session_dir = root / "2026-05-07_21-17-31_monitor"
    shutil.copytree(FIXTURE_SESSION, session_dir)
    return root


def test_scan_report_summaries_from_logs(packet_root: Path):
    reports = scan_report_summaries(packet_root)

    assert len(reports) == 1
    report = reports[0]
    assert report.report_id == "2026-05-07_21-17-31_monitor:1"
    assert report.complete is True
    assert report.file_count > 0
    assert report.battle_packet_count > 0
    assert report.rounds is None
    assert report.result is None


def test_get_report_summary_can_include_replay_result(packet_root: Path):
    report = get_report_summary("2026-05-07_21-17-31_monitor:1", packet_root)

    assert report.rounds == 17
    assert report.result is not None


def test_scan_battles_marks_unfinished_session(packet_root: Path):
    session_dir = packet_root / "2026-05-07_21-17-31_monitor"
    for fpath in session_dir.glob("*.bin"):
        meta = read_metadata(fpath) or {}
        if parse_opcode_hex(meta) == 0x132C:
            fpath.unlink()

    battles = scan_battles(session_dir)

    assert battles
    assert battles[0].incomplete is True


def test_build_report_package_contains_manifest_analysis_and_packets(packet_root: Path):
    rid = report_id("2026-05-07_21-17-31_monitor", 1)
    filename, payload = build_report_package(rid, packet_root)

    assert filename.endswith(".raco-report")
    with zipfile.ZipFile(BytesIO(payload)) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert "analysis.json" in names
        assert "README.txt" in names
        assert "packets/_session.json" in names
        assert any(name.startswith("packets/") and name.endswith(".bin") for name in names)

        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        analysis = json.loads(zf.read("analysis.json").decode("utf-8"))

    assert manifest["format"] == "raco-battle-report"
    assert manifest["format_version"] == 1
    assert manifest["report_id"] == rid
    assert analysis["total_packets"] == manifest["battle_packet_count"]
    assert analysis["final_state"]["round"] == 17
    json.dumps(analysis, ensure_ascii=False)


def test_archive_report_package_writes_cached_report(packet_root: Path, tmp_path: Path):
    archive_root = tmp_path / "archives"
    rid = report_id("2026-05-07_21-17-31_monitor", 1)

    archive_path = archive_report_package(rid, packet_root, archive_root)

    assert archive_path.is_file()
    assert find_archived_report(rid, archive_root) == archive_path
    filename, payload = get_report_package(rid, packet_root, archive_root)
    assert filename == archive_path.name
    assert payload == archive_path.read_bytes()


def test_archive_latest_completed_battle(packet_root: Path, tmp_path: Path):
    session_dir = packet_root / "2026-05-07_21-17-31_monitor"

    archive_path = archive_latest_completed_battle(session_dir, packet_root, tmp_path / "archives")

    assert archive_path is not None
    assert archive_path.is_file()


def test_scan_report_summaries_marks_archived_report(packet_root: Path, tmp_path: Path):
    archive_root = tmp_path / "archives"
    archive_report_package("2026-05-07_21-17-31_monitor:1", packet_root, archive_root)

    report = scan_report_summaries(packet_root, archive_root)[0]

    assert report.archived is True
    assert report.archive_path is not None


def test_report_analysis_matches_direct_replay(packet_root: Path):
    session_dir = packet_root / "2026-05-07_21-17-31_monitor"
    boundary = scan_battles(session_dir)[0]
    packets = load_battle_packets_for_window(session_dir, boundary)

    direct = build_report_analysis(packets)
    rid = report_id(session_dir.name, boundary.index)
    _, payload = build_report_package(rid, packet_root)

    with zipfile.ZipFile(BytesIO(payload)) as zf:
        analysis = json.loads(zf.read("analysis.json").decode("utf-8"))

    assert analysis["total_packets"] == direct["total_packets"]
    assert analysis["final_state"]["round"] == direct["final_state"]["round"]
    assert analysis["battle_summary"]["result"] == direct["battle_summary"]["result"]
