"""Battle report export helpers.

The report package is intended for support/debugging: it keeps the original
RC01 packet files intact and adds replay analysis that is easy to inspect.
"""
from __future__ import annotations

import io
import json
import os
import struct
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.analysis.constants import (
    IN_BATTLE_OPCODES,
    LIFECYCLE_OPCODES,
    OPCODE_BATTLE_ENTER,
    OPCODE_BATTLE_FINISH,
)
from src.analysis.battle_summary import compute_battle_summary
from src.analysis.battle_state import BattleStateTracker
from src.analysis.event_formatter import format_battle_event
from src.analysis.suggestions import build_state_suggestions
from src.protocol.opcodes import summarize
from src.protocol.proto_core import extract_inner_message, parse_record

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PACKET_ROOT = PROJECT_ROOT / "logs" / "packets"
DEFAULT_ARCHIVE_ROOT = PROJECT_ROOT / "logs" / "battle_reports"
REPORT_FORMAT_VERSION = 1
DEFAULT_PAD_BEFORE = 5.0
DEFAULT_PAD_AFTER = 2.0
DATA_CMD_PATTERN = "*_0x4013_*.bin"
MAGIC_V1 = b"RC01"
BATTLE_OPCODES = frozenset(LIFECYCLE_OPCODES | IN_BATTLE_OPCODES)


class BattleReportError(ValueError):
    """Raised when a requested report cannot be built."""


@dataclass(frozen=True)
class BattleBoundary:
    index: int
    enter_file: str
    finish_file: str
    enter_ts: str
    finish_ts: str
    enter_seconds: float
    finish_seconds: float
    incomplete: bool = False

    @property
    def duration(self) -> float:
        return max(0.0, self.finish_seconds - self.enter_seconds)


@dataclass(frozen=True)
class BattleReportSummary:
    report_id: str
    session_id: str
    battle_index: int
    enter_ts: str
    finish_ts: str
    duration_seconds: float
    complete: bool
    file_count: int
    battle_packet_count: int
    rounds: Optional[int]
    result: Optional[str]
    session_path: str
    archived: bool = False
    archive_path: Optional[str] = None


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


def count_battle_packet_files(files: List[Path]) -> int:
    count = 0
    for fpath in files:
        meta = read_metadata(fpath) or {}
        opcode = parse_opcode_hex(meta)
        if opcode in BATTLE_OPCODES:
            count += 1
    return count


def build_report_package(
    report_id_value: str,
    packet_root: Path = DEFAULT_PACKET_ROOT,
    *,
    pad_before: float = DEFAULT_PAD_BEFORE,
    pad_after: float = DEFAULT_PAD_AFTER,
) -> tuple[str, bytes]:
    """Build a .raco-report zip and return (filename, bytes)."""
    session_dir, boundary = resolve_report(report_id_value, packet_root)
    selected_files = select_packet_files(session_dir, boundary, pad_before=pad_before, pad_after=pad_after)
    if not selected_files:
        raise BattleReportError("No packet files found in battle window")

    packets = load_battle_packets_for_window(session_dir, boundary, pad_before=pad_before, pad_after=pad_after)
    analysis = build_report_analysis(packets, include_events=True)
    manifest = build_manifest(
        session_dir,
        boundary,
        selected_files,
        analysis,
        pad_before=pad_before,
        pad_after=pad_after,
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
        zf.writestr("analysis.json", json.dumps(analysis, ensure_ascii=False, indent=2, default=str))
        zf.writestr(
            "README.txt",
            "Raco Helper battle report.\n"
            "请把整个 .raco-report 文件发送给开发者用于战斗问题分析。\n"
            "packets/ 目录保留原始 RC01 抓包文件，analysis.json 为当前版本生成的结构化回放结果。\n",
        )
        session_meta = session_dir / "_session.json"
        if session_meta.exists():
            zf.write(session_meta, "packets/_session.json")
        for fpath in selected_files:
            zf.write(fpath, f"packets/{fpath.name}")

    filename = f"raco-report_{session_dir.name}_battle-{boundary.index}.raco-report"
    return filename, buffer.getvalue()


def report_filename(report_id_value: str) -> str:
    session_id, battle_index = parse_report_id(report_id_value)
    return f"raco-report_{session_id}_battle-{battle_index}.raco-report"


def report_archive_path(
    report_id_value: str,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
) -> Path:
    session_id, _battle_index = parse_report_id(report_id_value)
    return archive_root / session_id / report_filename(report_id_value)


def find_archived_report(
    report_id_value: str,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
) -> Optional[Path]:
    path = report_archive_path(report_id_value, archive_root)
    return path if path.is_file() else None


def get_report_package(
    report_id_value: str,
    packet_root: Path = DEFAULT_PACKET_ROOT,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
) -> tuple[str, bytes]:
    archived = find_archived_report(report_id_value, archive_root)
    if archived is not None:
        return archived.name, archived.read_bytes()
    return build_report_package(report_id_value, packet_root)


def archive_report_package(
    report_id_value: str,
    packet_root: Path = DEFAULT_PACKET_ROOT,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
    *,
    force: bool = False,
) -> Path:
    out_path = report_archive_path(report_id_value, archive_root)
    if out_path.is_file() and not force:
        return out_path

    filename, payload = build_report_package(report_id_value, packet_root)
    out_path = archive_root / parse_report_id(report_id_value)[0] / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp_path.write_bytes(payload)
    os.replace(tmp_path, out_path)
    return out_path


def archive_latest_completed_battle(
    session_dir: Path,
    packet_root: Path = DEFAULT_PACKET_ROOT,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
    *,
    force: bool = False,
) -> Optional[Path]:
    session_dir = session_dir.resolve()
    packet_root = packet_root.resolve()
    try:
        session_dir.relative_to(packet_root)
    except ValueError as exc:
        raise BattleReportError("Session path is outside packet root") from exc

    completed = [boundary for boundary in scan_battles(session_dir) if not boundary.incomplete]
    if not completed:
        return None
    boundary = completed[-1]
    return archive_report_package(
        report_id(session_dir.name, boundary.index),
        packet_root=packet_root,
        archive_root=archive_root,
        force=force,
    )


def build_manifest(
    session_dir: Path,
    boundary: BattleBoundary,
    selected_files: List[Path],
    analysis: Dict[str, Any],
    *,
    pad_before: float,
    pad_after: float,
) -> Dict[str, Any]:
    final_state = analysis.get("final_state", {})
    return {
        "format": "raco-battle-report",
        "format_version": REPORT_FORMAT_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_session": session_dir.name,
        "report_id": report_id(session_dir.name, boundary.index),
        "battle_index": boundary.index,
        "complete": not boundary.incomplete,
        "window": {
            "enter_ts": boundary.enter_ts,
            "finish_ts": boundary.finish_ts,
            "duration_seconds": round(boundary.duration, 3),
            "pad_before": pad_before,
            "pad_after": pad_after,
            "enter_file": boundary.enter_file,
            "finish_file": boundary.finish_file,
        },
        "files": [fpath.name for fpath in selected_files],
        "file_count": len(selected_files),
        "battle_packet_count": analysis.get("total_packets", 0),
        "analysis": {
            "rounds": final_state.get("round"),
            "result": final_state.get("result"),
            "stopped_early": analysis.get("stopped_early", False),
        },
    }


def build_report_analysis(
    packets: List[Dict[str, Any]],
    *,
    include_events: bool = True,
) -> Dict[str, Any]:
    """Build a compact replay analysis without storing full per-event state copies."""
    tracker = BattleStateTracker()
    events: List[Dict[str, Any]] = []
    rounds: Dict[int, Dict[str, Any]] = {}
    messages: List[Dict[str, Any]] = []

    for index, item in enumerate(packets):
        record = item["record"]
        opcode = item["opcode"]
        inner = extract_inner_message(record.get("root", {})) if opcode == 0x0414 else None
        kind, summary = summarize(record, inner)
        detail = summary.get("detail", summary) if isinstance(summary, dict) else {}
        if not isinstance(detail, dict):
            detail = {}

        state = tracker.handle_event(opcode, detail)
        round_num = state.get("round", 0)
        formatted_events = [
            event.to_dict()
            for event in format_battle_event(opcode, detail, state, round_num)
        ]
        suggestions = build_state_suggestions(state)
        event_messages = compact_messages(opcode, state, formatted_events, suggestions)
        messages.extend(event_messages)

        round_bucket = rounds.setdefault(
            round_num,
            {
                "round_num": round_num,
                "formatted_events": [],
                "suggestions": [],
                "messages": [],
            },
        )
        round_bucket["formatted_events"].extend(formatted_events)
        round_bucket["suggestions"].extend(suggestions)
        round_bucket["messages"].extend(event_messages)

        if include_events:
            events.append(
                {
                    "index": index,
                    "opcode": opcode,
                    "kind": kind,
                    "round_num": round_num,
                    "filename": item.get("filename"),
                    "formatted_events": formatted_events,
                    "suggestions": suggestions,
                    "messages": event_messages,
                }
            )

    final_state = tracker.get_state()
    return {
        "total_packets": len(packets),
        "stopped_early": False,
        "rounds": [rounds[key] for key in sorted(rounds)],
        "events": events,
        "final_state": final_state,
        "battle_summary": compute_battle_summary(final_state),
        "messages": messages,
    }


def compact_messages(
    opcode: int,
    state: Dict[str, Any],
    formatted_events: List[Dict[str, Any]],
    suggestions: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    if len(formatted_events) == 1:
        messages.append({"type": "battle_event", "event": formatted_events[0]})
    elif len(formatted_events) > 1:
        messages.append({"type": "battle_events", "events": formatted_events})

    messages.append({
        "type": "state_update",
        "round": state.get("round", 0),
        "phase": state.get("phase"),
        "result": state.get("result"),
        "my_active": _pet_ref(state.get("my_active")),
        "opp_active": _pet_ref(state.get("opp_active")),
    })

    if suggestions:
        messages.append({"type": "suggestions", "suggestions": suggestions})
    if opcode == OPCODE_BATTLE_FINISH:
        messages.append({"type": "battle_summary", "summary": compute_battle_summary(state)})
    return messages


def _pet_ref(pet: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not pet:
        return None
    return {
        "pet_id": pet.get("pet_id"),
        "base_id": pet.get("base_id"),
        "battle_uid": pet.get("battle_uid"),
        "name": pet.get("name"),
        "current_hp": pet.get("current_hp"),
        "max_hp": pet.get("max_hp"),
        "energy": pet.get("energy"),
    }


def scan_battles(session_dir: Path) -> List[BattleBoundary]:
    candidates = sorted(
        session_dir.glob(DATA_CMD_PATTERN),
        key=lambda p: _extract_timestamp(p.name),
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
        ts_raw = _extract_timestamp(fpath.name)
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
            last_ts_raw = _extract_timestamp(last_file.name)
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
    for fpath in sorted(session_dir.glob("*.bin"), key=lambda p: _extract_timestamp(p.name)):
        ts_raw = _extract_timestamp(fpath.name)
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
    for fpath in sorted(session_dir.glob("*.bin"), key=lambda p: _extract_timestamp(p.name)):
        ts_raw = _extract_timestamp(fpath.name)
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


def read_bin_packet(filepath: Path) -> Dict[str, Any]:
    with open(filepath, "rb") as f:
        magic = f.read(4)
        if magic != MAGIC_V1:
            raise BattleReportError(f"Invalid packet magic in {filepath.name}")
        cmd = struct.unpack(">H", f.read(2))[0]
        seq = struct.unpack(">I", f.read(4))[0]
        direction = f.read(4).rstrip(b"\x00").decode("ascii")
        header_extra_len = struct.unpack(">I", f.read(4))[0]
        header_extra = f.read(header_extra_len)
        body_len = struct.unpack(">I", f.read(4))[0]
        body = f.read(body_len)
        decrypted_len = struct.unpack(">I", f.read(4))[0]
        decrypted_body = f.read(decrypted_len) if decrypted_len > 0 else None
        meta_len = struct.unpack(">I", f.read(4))[0]
        metadata = json.loads(f.read(meta_len).decode("utf-8")) if meta_len else {}

    return {
        "cmd": cmd,
        "direction": direction,
        "seq": seq,
        "body_len": body_len,
        "header_extra_hex": header_extra.hex(),
        "body_hex": body.hex(),
        "decrypted_body_hex": decrypted_body.hex() if decrypted_body else "",
        "_metadata": metadata,
    }


def read_metadata(filepath: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(filepath, "rb") as f:
            if f.read(4) != MAGIC_V1:
                return None
            f.read(2)
            f.read(4)
            f.read(4)
            header_extra_len = struct.unpack(">I", f.read(4))[0]
            f.read(header_extra_len)
            body_len = struct.unpack(">I", f.read(4))[0]
            f.read(body_len)
            decrypted_len = struct.unpack(">I", f.read(4))[0]
            f.read(decrypted_len)
            meta_len = struct.unpack(">I", f.read(4))[0]
            if meta_len <= 0 or meta_len > 1_000_000:
                return None
            return json.loads(f.read(meta_len).decode("utf-8"))
    except Exception:
        return None


def parse_opcode_hex(meta: Dict[str, Any]) -> Optional[int]:
    opcode_hex = meta.get("opcode_hex")
    if not opcode_hex:
        return None
    try:
        return int(opcode_hex, 16)
    except ValueError:
        return None


def _extract_timestamp(filename: str) -> str:
    parts = filename.rsplit("_", 1)
    if len(parts) == 2:
        return parts[1].replace(".bin", "")
    return ""


def ts_to_seconds(ts: str) -> float:
    ts = ts.strip()
    return int(ts[0:2]) * 3600 + int(ts[2:4]) * 60 + float(ts[4:])
