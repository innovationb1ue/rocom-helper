from __future__ import annotations

import json
import shutil
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from src.analysis.battle_report import build_report_package as facade_build_report_package
from src.analysis.reporting.lookup import report_id
from src.analysis.reporting.package import (
    archive_latest_completed_battle,
    archive_report_package,
    build_report_package,
    find_archived_report,
    get_report_package,
    report_archive_path,
    report_filename,
)

FIXTURE_SESSION = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"


@pytest.fixture()
def packet_root(tmp_path: Path) -> Path:
    if not FIXTURE_SESSION.exists():
        pytest.skip("battle_session_1 fixture not found")
    root = tmp_path / "logs" / "packets"
    shutil.copytree(FIXTURE_SESSION, root / "2026-05-07_21-17-31_monitor")
    return root


def test_package_build_matches_facade_and_keeps_original_packets(packet_root: Path):
    rid = report_id("2026-05-07_21-17-31_monitor", 1)

    direct_name, direct_payload = build_report_package(rid, packet_root)
    facade_name, facade_payload = facade_build_report_package(rid, packet_root)

    assert direct_name == facade_name
    with zipfile.ZipFile(BytesIO(direct_payload)) as zf:
        names = set(zf.namelist())
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    with zipfile.ZipFile(BytesIO(facade_payload)) as zf:
        facade_names = set(zf.namelist())
        facade_manifest = json.loads(zf.read("manifest.json").decode("utf-8"))

    assert names == facade_names
    assert {
        key: value
        for key, value in manifest.items()
        if key != "generated_at"
    } == {
        key: value
        for key, value in facade_manifest.items()
        if key != "generated_at"
    }
    assert "README.txt" in names
    assert "packets/_session.json" in names
    assert manifest["format"] == "raco-battle-report"
    assert manifest["format_version"] == 2
    assert manifest["battle_packet_count"] == 227


def test_package_archive_helpers_read_cached_report(packet_root: Path, tmp_path: Path):
    archive_root = tmp_path / "archives"
    rid = report_id("2026-05-07_21-17-31_monitor", 1)

    assert report_filename(rid).endswith(".raco-report")
    assert report_archive_path(rid, archive_root).parent.name == "2026-05-07_21-17-31_monitor"

    archive_path = archive_report_package(rid, packet_root, archive_root)
    filename, payload = get_report_package(rid, packet_root, archive_root)

    assert find_archived_report(rid, archive_root) == archive_path
    assert filename == archive_path.name
    assert payload == archive_path.read_bytes()


def test_archive_latest_completed_battle_uses_latest_complete_boundary(packet_root: Path, tmp_path: Path):
    session_dir = packet_root / "2026-05-07_21-17-31_monitor"

    archive_path = archive_latest_completed_battle(session_dir, packet_root, tmp_path / "archives")

    assert archive_path is not None
    assert archive_path.is_file()
