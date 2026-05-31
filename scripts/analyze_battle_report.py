"""Import a .raco-report and generate local battle analysis outputs.

Usage:
    py -m scripts.analyze_battle_report path/to/battle.raco-report --output tmp/received_reports
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.generate_battle_report import generate_report_from_result, replay_result_to_dict
from scripts.unpack_battle_report import ReportUnpackError, unpack_report
from src.analysis.replay_runner import BattleReplayRunner
from tests.packet_reader import load_battle_packets


DEFAULT_OUTPUT_ROOT = _PROJECT_ROOT / "tmp" / "received_reports"


@dataclass(frozen=True)
class AnalyzeReportResult:
    output_dir: Path
    packet_dir: Path
    text_report_path: Path
    analysis_json_path: Path
    summary: Dict[str, Any]


def _report_stem(report_path: Path) -> str:
    suffix = ".raco-report"
    name = report_path.name
    return name[: -len(suffix)] if name.endswith(suffix) else report_path.stem


def analyze_report(
    report_path: Path,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    *,
    force: bool = False,
) -> AnalyzeReportResult:
    """Unpack, replay, and render a received .raco-report."""
    report_path = report_path.resolve()
    output_root = output_root.resolve()
    output_dir = output_root / _report_stem(report_path)
    packet_dir = output_dir / "packets"

    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise ReportUnpackError(f"Output directory is not empty: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    unpack_report(report_path, packet_dir, force=force)

    packets = load_battle_packets(packet_dir)
    if not packets:
        raise ReportUnpackError(f"No replayable battle packets found in: {packet_dir}")

    result = BattleReplayRunner().run(packets)
    analysis = replay_result_to_dict(result)

    text_report_path = output_dir / "battle_report.txt"
    analysis_json_path = output_dir / "analysis.json"
    text_report_path.write_text(generate_report_from_result(result), encoding="utf-8")
    analysis_json_path.write_text(
        json.dumps(analysis, default=str, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = {
        "total_packets": result.total_packets,
        "rounds": len(result.rounds),
        "final_round": result.final_state.get("round"),
        "result": result.battle_summary.get("result"),
        "my_pets": len(result.final_state.get("my_pets", [])),
        "opp_pets": len(result.final_state.get("opp_pets", [])),
    }
    return AnalyzeReportResult(
        output_dir=output_dir,
        packet_dir=packet_dir,
        text_report_path=text_report_path,
        analysis_json_path=analysis_json_path,
        summary=summary,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a received .raco-report locally")
    parser.add_argument("report", type=Path, help="Path to .raco-report")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Root directory for unpacked packets and generated analysis",
    )
    parser.add_argument("--force", action="store_true", help="Allow writing into an existing output directory")
    args = parser.parse_args()

    try:
        result = analyze_report(args.report, args.output, force=args.force)
    except ReportUnpackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Battle report analysis: PASS")
    print(
        "  packets={total_packets} rounds={rounds} final_round={final_round} "
        "result={result} my_pets={my_pets} opp_pets={opp_pets}".format(**result.summary)
    )
    print(f"  output={result.output_dir}")
    print(f"  packets_dir={result.packet_dir}")
    print(f"  report={result.text_report_path}")
    print(f"  analysis={result.analysis_json_path}")


if __name__ == "__main__":
    main()
