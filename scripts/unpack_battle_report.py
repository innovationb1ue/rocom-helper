"""Unpack a .raco-report into a replayable packet directory.

Usage:
    py -m scripts.unpack_battle_report path/to/report.raco-report
    py -m scripts.unpack_battle_report path/to/report.raco-report --output tmp/report_packets --verify
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class ReportUnpackError(ValueError):
    """Raised when a .raco-report cannot be unpacked safely."""


def _default_output_dir(report_path: Path) -> Path:
    name = report_path.name
    suffix = ".raco-report"
    stem = name[: -len(suffix)] if name.endswith(suffix) else report_path.stem
    return report_path.parent / stem


def _safe_packet_relpath(member_name: str) -> Optional[Path]:
    posix_path = PurePosixPath(member_name)
    parts = posix_path.parts
    if len(parts) < 2 or parts[0] != "packets":
        return None
    rel_parts = parts[1:]
    if any(part in ("", ".", "..") for part in rel_parts):
        raise ReportUnpackError(f"Unsafe report member path: {member_name}")
    return Path(*rel_parts)


def _read_manifest(zf: zipfile.ZipFile) -> Dict[str, Any]:
    try:
        raw = zf.read("manifest.json")
    except KeyError as exc:
        raise ReportUnpackError("manifest.json not found in report") from exc
    manifest = json.loads(raw.decode("utf-8"))
    if manifest.get("format") != "raco-battle-report":
        raise ReportUnpackError("Unsupported report format")
    return manifest


def unpack_report(report_path: Path, output_dir: Optional[Path] = None, *, force: bool = False) -> Path:
    """Extract report packets into a directory accepted by load_battle_packets()."""
    report_path = report_path.resolve()
    if not report_path.is_file():
        raise ReportUnpackError(f"Report not found: {report_path}")

    output_dir = (output_dir or _default_output_dir(report_path)).resolve()
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise ReportUnpackError(f"Output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    packet_count = 0
    with zipfile.ZipFile(report_path) as zf:
        manifest = _read_manifest(zf)
        for member in zf.infolist():
            rel_path = _safe_packet_relpath(member.filename)
            if rel_path is None or member.is_dir():
                continue
            dest = output_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(member))
            if dest.suffix == ".bin":
                packet_count += 1

    if packet_count == 0:
        raise ReportUnpackError("No packet .bin files found in report")

    manifest_path = output_dir / "_raco_report_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_dir


def verify_replay(packet_dir: Path, *, full_analysis: bool = False) -> Dict[str, Any]:
    """Run a headless replay from an unpacked packet directory."""
    from tests.packet_reader import load_battle_packets
    from src.analysis.replay_runner import BattleReplayRunner

    packets = load_battle_packets(packet_dir)
    if not packets:
        raise ReportUnpackError(f"No battle packets found in: {packet_dir}")

    result = BattleReplayRunner(
        include_analysis=full_analysis,
        include_hooks=full_analysis,
        include_formatting=full_analysis,
    ).run(packets)
    return {
        "total_packets": result.total_packets,
        "rounds": len(result.rounds),
        "final_round": result.final_state.get("round"),
        "result": result.battle_summary.get("result"),
        "my_pets": len(result.final_state.get("my_pets", [])),
        "opp_pets": len(result.final_state.get("opp_pets", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Unpack a .raco-report into a replayable packet directory")
    parser.add_argument("report", type=Path, help="Path to .raco-report")
    parser.add_argument("--output", type=Path, default=None, help="Output packet directory")
    parser.add_argument("--force", action="store_true", help="Allow writing into a non-empty output directory")
    parser.add_argument("--verify", action="store_true", help="Run headless replay after unpacking")
    args = parser.parse_args()

    try:
        out_dir = unpack_report(args.report, args.output, force=args.force)
        print(f"Unpacked packets to: {out_dir}")
        if args.verify:
            summary = verify_replay(out_dir)
            print("Replay verification: PASS")
            print(
                "  packets={total_packets} rounds={rounds} final_round={final_round} "
                "result={result} my_pets={my_pets} opp_pets={opp_pets}".format(**summary)
            )
    except ReportUnpackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
