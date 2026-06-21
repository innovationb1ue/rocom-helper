"""战斗报告的会话扫描与窗口包加载。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from src.analysis.constants import (
    AUX_BATTLE_OPCODES,
    IN_BATTLE_OPCODES,
    LIFECYCLE_OPCODES,
    OPCODE_BATTLE_ENTER,
    OPCODE_BATTLE_FINISH,
)
from src.analysis.reporting.models import BattleBoundary
from src.analysis.reporting.packet_io import (
    DATA_CMD_PATTERN,
    extract_timestamp,
    parse_opcode_hex,
    read_bin_packet,
    read_metadata,
    ts_to_seconds,
)
from src.protocol.proto_core import parse_record

DEFAULT_PAD_BEFORE = 10.0
DEFAULT_PAD_AFTER = 5.0
BATTLE_OPCODES = frozenset(LIFECYCLE_OPCODES | IN_BATTLE_OPCODES | AUX_BATTLE_OPCODES)


def count_battle_packet_files(files: List[Path]) -> int:
    count = 0
    for fpath in files:
        meta = read_metadata(fpath) or {}
        opcode = parse_opcode_hex(meta)
        if opcode in BATTLE_OPCODES:
            count += 1
    return count


def scan_battles(session_dir: Path) -> List[BattleBoundary]:
    candidates = sorted(
        session_dir.glob(DATA_CMD_PATTERN),
        key=lambda p: extract_timestamp(p.name),
    )
    enters: List[tuple[str, str, float]] = []
    finishes: List[tuple[str, str, float]] = []

    for fpath in candidates:
        meta = read_metadata(fpath)
        if not meta:
            continue
        opcode = parse_opcode_hex(meta)
        if opcode is None:
            continue
        ts_raw = extract_timestamp(fpath.name)
        if not ts_raw:
            continue
        ts_display = meta.get("ts", ts_raw)
        ts_seconds = ts_to_seconds(ts_raw)
        if opcode == OPCODE_BATTLE_ENTER:
            enters.append((fpath.name, ts_display, ts_seconds))
        elif opcode == OPCODE_BATTLE_FINISH:
            finishes.append((fpath.name, ts_display, ts_seconds))

    if not enters:
        return []

    boundaries: List[BattleBoundary] = []
    finish_idx = 0
    for idx, (enter_file, enter_ts, enter_seconds) in enumerate(enters, start=1):
        paired = False
        while finish_idx < len(finishes):
            finish_file, finish_ts, finish_seconds = finishes[finish_idx]
            finish_idx += 1
            if finish_seconds >= enter_seconds:
                boundaries.append(
                    BattleBoundary(
                        index=idx,
                        enter_file=enter_file,
                        finish_file=finish_file,
                        enter_ts=enter_ts,
                        finish_ts=finish_ts,
                        enter_seconds=enter_seconds,
                        finish_seconds=finish_seconds,
                    )
                )
                paired = True
                break

        if not paired and candidates:
            last_file = candidates[-1]
            last_ts_raw = extract_timestamp(last_file.name)
            last_meta = read_metadata(last_file) or {}
            boundaries.append(
                BattleBoundary(
                    index=idx,
                    enter_file=enter_file,
                    finish_file=last_file.name,
                    enter_ts=enter_ts,
                    finish_ts=last_meta.get("ts", last_ts_raw),
                    enter_seconds=enter_seconds,
                    finish_seconds=ts_to_seconds(last_ts_raw),
                    incomplete=True,
                )
            )

    return boundaries


def select_packet_files(
    session_dir: Path,
    boundary: BattleBoundary,
    *,
    pad_before: float = DEFAULT_PAD_BEFORE,
    pad_after: float = DEFAULT_PAD_AFTER,
) -> List[Path]:
    window_start = boundary.enter_seconds - pad_before
    window_end = boundary.finish_seconds + pad_after
    selected: List[Path] = []
    for fpath in sorted(session_dir.glob("*.bin"), key=lambda p: extract_timestamp(p.name)):
        ts_raw = extract_timestamp(fpath.name)
        if not ts_raw:
            continue
        ts = ts_to_seconds(ts_raw)
        if window_start <= ts <= window_end:
            selected.append(fpath)
    return selected


def load_battle_packets_for_window(
    session_dir: Path,
    boundary: BattleBoundary,
    *,
    pad_before: float = DEFAULT_PAD_BEFORE,
    pad_after: float = DEFAULT_PAD_AFTER,
) -> List[Dict[str, Any]]:
    window_start = boundary.enter_seconds - pad_before
    window_end = boundary.finish_seconds + pad_after
    packets: List[Dict[str, Any]] = []
    for fpath in sorted(session_dir.glob("*.bin"), key=lambda p: extract_timestamp(p.name)):
        ts_raw = extract_timestamp(fpath.name)
        if not ts_raw:
            continue
        ts = ts_to_seconds(ts_raw)
        if not window_start <= ts <= window_end:
            continue
        meta = read_metadata(fpath) or {}
        opcode_hint = parse_opcode_hex(meta)
        if opcode_hint is not None and opcode_hint not in BATTLE_OPCODES:
            continue
        pkt = read_bin_packet(fpath)
        if pkt["cmd"] != 0x4013 or not pkt["decrypted_body_hex"]:
            continue
        record = parse_record(pkt)
        if record is None:
            continue
        opcode = record.get("opcode", 0)
        if opcode not in BATTLE_OPCODES:
            continue
        packets.append({"packet": pkt, "record": record, "opcode": opcode, "filename": fpath.name})
    return packets

