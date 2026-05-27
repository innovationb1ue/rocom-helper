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
    build_report_package,
    count_battle_packet_files,
    find_archived_report,
    get_report_summary,
    get_report_package,
    parse_opcode_hex,
    read_metadata,
    report_id,
    scan_battles,
    scan_report_summaries,
)
from scripts.unpack_battle_report import unpack_report, verify_replay


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


def test_build_report_package_contains_manifest_and_original_packets(packet_root: Path):
    rid = report_id("2026-05-07_21-17-31_monitor", 1)
    filename, payload = build_report_package(rid, packet_root)
    session_dir = packet_root / "2026-05-07_21-17-31_monitor"

    assert filename.endswith(".raco-report")
    with zipfile.ZipFile(BytesIO(payload)) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert "analysis.json" not in names
        assert "README.txt" in names
        assert "packets/_session.json" in names
        packet_names = sorted(name for name in names if name.startswith("packets/") and name.endswith(".bin"))
        assert packet_names

        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        readme = zf.read("README.txt").decode("utf-8")
        for packet_name in packet_names:
            source_name = Path(packet_name).name
            assert zf.read(packet_name) == (session_dir / source_name).read_bytes()

    assert manifest["format"] == "raco-battle-report"
    assert manifest["format_version"] == 2
    assert manifest["report_id"] == rid
    assert "analysis" not in manifest
    assert manifest["window"]["pad_before"] == 10.0
    assert manifest["window"]["pad_after"] == 5.0
    assert manifest["file_count"] == len(packet_names)
    assert set(manifest["files"]) == {Path(name).name for name in packet_names}
    assert manifest["battle_packet_count"] == count_battle_packet_files(
        [session_dir / Path(name).name for name in packet_names]
    )
    assert "original RC01 packet files" in readme


def test_archive_report_package_writes_cached_report(packet_root: Path, tmp_path: Path):
    archive_root = tmp_path / "archives"
    rid = report_id("2026-05-07_21-17-31_monitor", 1)

    archive_path = archive_report_package(rid, packet_root, archive_root)

    assert archive_path.is_file()
    assert find_archived_report(rid, archive_root) == archive_path
    filename, payload = get_report_package(rid, packet_root, archive_root)
    assert filename == archive_path.name
    assert payload == archive_path.read_bytes()


def test_unpack_report_restores_replayable_packet_dir(packet_root: Path, tmp_path: Path):
    rid = report_id("2026-05-07_21-17-31_monitor", 1)
    filename, payload = build_report_package(rid, packet_root)
    report_path = tmp_path / filename
    report_path.write_bytes(payload)

    out_dir = unpack_report(report_path, tmp_path / "unpacked")

    assert (out_dir / "_session.json").is_file()
    assert (out_dir / "_raco_report_manifest.json").is_file()
    assert list(out_dir.glob("*.bin"))

    summary = verify_replay(out_dir)
    assert summary["total_packets"] > 0
    assert summary["final_round"] == 17
    assert summary["result"] == "WIN_HP"
    assert summary["my_pets"] == 6
    assert summary["opp_pets"] == 6


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
