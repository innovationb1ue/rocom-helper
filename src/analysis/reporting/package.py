"""战斗报告 zip 打包与归档。"""
from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.analysis.reporting.config import (
    DEFAULT_ARCHIVE_ROOT,
    DEFAULT_PACKET_ROOT,
    REPORT_FORMAT_VERSION,
)
from src.analysis.reporting.lookup import parse_report_id, report_id, resolve_report
from src.analysis.reporting.models import BattleBoundary, BattleReportError
from src.analysis.reporting.window import (
    DEFAULT_PAD_AFTER,
    DEFAULT_PAD_BEFORE,
    count_battle_packet_files,
    scan_battles,
    select_packet_files,
)


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

    manifest = build_manifest(
        session_dir,
        boundary,
        selected_files,
        pad_before=pad_before,
        pad_after=pad_after,
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
        zf.writestr("README.txt", _report_readme())
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
    *,
    pad_before: float,
    pad_after: float,
) -> Dict[str, Any]:
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
        "battle_packet_count": count_battle_packet_files(selected_files),
    }


def _report_readme() -> str:
    return (
        "Raco Helper battle report.\n"
        "This .raco-report keeps original RC01 packet files for battle debugging.\n"
        "Extract packets/ and replay the .bin files to reproduce the full battle.\n"
        "manifest.json records the source session, battle boundary, export window, and file list.\n"
    )

