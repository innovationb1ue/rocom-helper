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
    build_report_diagnostics,
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
from scripts.analyze_battle_report import analyze_report


FIXTURE_SESSION = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"


@pytest.fixture(scope="module")
def packet_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if not FIXTURE_SESSION.exists():
        pytest.skip("battle_session_1 fixture not found")
    root = tmp_path_factory.mktemp("packet_logs") / "logs" / "packets"
    session_dir = root / "2026-05-07_21-17-31_monitor"
    shutil.copytree(FIXTURE_SESSION, session_dir)
    return root


@pytest.fixture()
def destructive_packet_root(tmp_path: Path) -> Path:
    if not FIXTURE_SESSION.exists():
        pytest.skip("battle_session_1 fixture not found")
    root = tmp_path / "logs" / "packets"
    session_dir = root / "2026-05-07_21-17-31_monitor"
    shutil.copytree(FIXTURE_SESSION, session_dir)
    return root


@pytest.fixture(scope="module")
def report_package(packet_root: Path):
    rid = report_id("2026-05-07_21-17-31_monitor", 1)
    return build_report_package(rid, packet_root)


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


def test_build_report_diagnostics_for_missing_packet_root(tmp_path: Path):
    diagnostics = build_report_diagnostics(tmp_path / "missing" / "packets")

    assert diagnostics.report_count == 0
    assert diagnostics.packet_session_count == 0
    assert diagnostics.packet_file_count == 0
    assert diagnostics.latest_session_id is None
    assert diagnostics.has_battle_enter is False
    assert diagnostics.has_battle_finish is False


def test_build_report_diagnostics_for_empty_session(tmp_path: Path):
    packet_root = tmp_path / "logs" / "packets"
    (packet_root / "2026-05-31_12-00-00_monitor").mkdir(parents=True)

    diagnostics = build_report_diagnostics(packet_root)

    assert diagnostics.report_count == 0
    assert diagnostics.packet_session_count == 1
    assert diagnostics.packet_file_count == 0
    assert diagnostics.latest_session_id == "2026-05-31_12-00-00_monitor"
    assert diagnostics.latest_session_file_count == 0
    assert diagnostics.has_battle_enter is False
    assert diagnostics.has_battle_finish is False


def test_build_report_diagnostics_for_complete_fixture(packet_root: Path):
    diagnostics = build_report_diagnostics(packet_root)

    assert diagnostics.report_count == 1
    assert diagnostics.packet_session_count == 1
    assert diagnostics.packet_file_count > 0
    assert diagnostics.battle_enter_count == 1
    assert diagnostics.battle_finish_count == 1
    assert diagnostics.completed_battle_count == 1
    assert diagnostics.incomplete_battle_count == 0
    assert diagnostics.has_battle_enter is True
    assert diagnostics.has_battle_finish is True


def test_get_report_summary_can_include_replay_result(packet_root: Path):
    report = get_report_summary("2026-05-07_21-17-31_monitor:1", packet_root)

    assert report.rounds == 17
    assert report.result is not None


def test_scan_battles_marks_unfinished_session(destructive_packet_root: Path):
    session_dir = destructive_packet_root / "2026-05-07_21-17-31_monitor"
    for fpath in session_dir.glob("*.bin"):
        meta = read_metadata(fpath) or {}
        if parse_opcode_hex(meta) == 0x132C:
            fpath.unlink()

    battles = scan_battles(session_dir)

    assert battles
    assert battles[0].incomplete is True


def test_build_report_package_allows_unfinished_session(destructive_packet_root: Path):
    session_dir = destructive_packet_root / "2026-05-07_21-17-31_monitor"
    for fpath in session_dir.glob("*.bin"):
        meta = read_metadata(fpath) or {}
        if parse_opcode_hex(meta) == 0x132C:
            fpath.unlink()

    battles = scan_battles(session_dir)
    assert battles
    assert battles[0].incomplete is True

    filename, payload = build_report_package(
        report_id("2026-05-07_21-17-31_monitor", 1),
        destructive_packet_root,
    )

    assert filename.endswith(".raco-report")
    with zipfile.ZipFile(BytesIO(payload)) as zf:
        names = set(zf.namelist())
        packet_names = sorted(name for name in names if name.startswith("packets/") and name.endswith(".bin"))
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))

    assert packet_names
    assert manifest["complete"] is False
    assert manifest["battle_packet_count"] > 0
    assert manifest["file_count"] == len(packet_names)


def test_build_report_diagnostics_for_unfinished_fixture(destructive_packet_root: Path):
    session_dir = destructive_packet_root / "2026-05-07_21-17-31_monitor"
    for fpath in session_dir.glob("*.bin"):
        meta = read_metadata(fpath) or {}
        if parse_opcode_hex(meta) == 0x132C:
            fpath.unlink()

    diagnostics = build_report_diagnostics(destructive_packet_root)

    assert diagnostics.report_count == 1
    assert diagnostics.battle_enter_count == 1
    assert diagnostics.battle_finish_count == 0
    assert diagnostics.completed_battle_count == 0
    assert diagnostics.incomplete_battle_count == 1
    assert diagnostics.has_battle_enter is True
    assert diagnostics.has_battle_finish is False


def test_build_report_package_contains_manifest_and_original_packets(
    packet_root: Path,
    report_package,
):
    filename, payload = report_package
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
    assert manifest["report_id"] == report_id("2026-05-07_21-17-31_monitor", 1)
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


def test_unpack_report_restores_replayable_packet_dir(report_package, tmp_path: Path):
    filename, payload = report_package
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


def test_analyze_report_unpacks_verifies_and_writes_outputs(report_package, tmp_path: Path):
    filename, payload = report_package
    report_path = tmp_path / filename
    report_path.write_bytes(payload)

    result = analyze_report(report_path, tmp_path / "received_reports")

    assert result.output_dir.is_dir()
    assert result.packet_dir.is_dir()
    assert result.text_report_path.is_file()
    assert result.analysis_json_path.is_file()
    assert result.summary["total_packets"] > 0
    assert result.summary["final_round"] == 17
    assert result.summary["result"] == "WIN_HP"
    assert "洛克王国 PvP 对战回放报告" in result.text_report_path.read_text(encoding="utf-8")
    analysis = json.loads(result.analysis_json_path.read_text(encoding="utf-8"))
    assert analysis["battle_summary"]["result"] == "WIN_HP"


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
