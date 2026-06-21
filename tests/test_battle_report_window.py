from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from src.analysis.battle_report import scan_battles as facade_scan_battles
from src.analysis.reporting.packet_io import extract_timestamp, parse_opcode_hex, read_bin_packet, read_metadata, ts_to_seconds
from src.analysis.reporting.window import (
    BATTLE_OPCODES,
    count_battle_packet_files,
    load_battle_packets_for_window,
    scan_battles,
    select_packet_files,
)

FIXTURE_SESSION = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"


@pytest.fixture()
def session_dir(tmp_path: Path) -> Path:
    if not FIXTURE_SESSION.exists():
        pytest.skip("battle_session_1 fixture not found")
    out = tmp_path / "2026-05-07_21-17-31_monitor"
    shutil.copytree(FIXTURE_SESSION, out)
    return out


def test_packet_io_reads_rc01_metadata_and_packet(session_dir: Path):
    packet_file = next(
        fpath
        for fpath in session_dir.glob("*_0x4013_*.bin")
        if parse_opcode_hex(read_metadata(fpath) or {}) in BATTLE_OPCODES
    )

    meta = read_metadata(packet_file)
    packet = read_bin_packet(packet_file)

    assert meta is not None
    assert parse_opcode_hex(meta) in BATTLE_OPCODES
    assert packet["cmd"] == 0x4013
    assert packet["direction"] in {"c2s", "s2c"}
    assert extract_timestamp(packet_file.name)
    assert ts_to_seconds(extract_timestamp(packet_file.name)) > 0


def test_window_scanner_is_independent_and_matches_facade(session_dir: Path):
    direct = scan_battles(session_dir)
    through_facade = facade_scan_battles(session_dir)

    assert direct == through_facade
    assert len(direct) == 1
    boundary = direct[0]
    assert boundary.index == 1
    assert boundary.incomplete is False
    assert boundary.duration > 0


def test_window_file_selection_and_packet_loading(session_dir: Path):
    boundary = scan_battles(session_dir)[0]

    selected_files = select_packet_files(session_dir, boundary)
    packets = load_battle_packets_for_window(session_dir, boundary)

    selected_names = {fpath.name for fpath in selected_files}
    assert boundary.enter_file in selected_names
    assert boundary.finish_file in selected_names
    assert count_battle_packet_files(selected_files) == len(packets)
    assert packets
    assert {packet["opcode"] for packet in packets}.issubset(BATTLE_OPCODES)
