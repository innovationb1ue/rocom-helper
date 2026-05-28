"""回放伤害预测对账 CLI。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.analysis.damage_audit import build_damage_audit, build_multi_session_damage_audit
from src.analysis.replay_runner import BattleReplayRunner
from tests.packet_reader import load_battle_packets


def _resolve_session_dir(session: str) -> Path:
    """按字面路径、fixture 名称、运行日志名称的顺序解析回放目录。"""
    direct = Path(session)
    if direct.is_dir():
        return direct
    fixture = Path("tests") / "fixtures" / "packets" / session
    if fixture.is_dir():
        return fixture
    log_dir = Path("logs") / "packets" / session
    if log_dir.is_dir():
        return log_dir
    return fixture


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit replay damage predictions")
    parser.add_argument("--session", default="battle_session_1")
    parser.add_argument(
        "--sessions",
        nargs="+",
        help="Audit several replay sessions and print an aggregate report",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    args = parser.parse_args()

    sessions = args.sessions or [args.session]
    reports = {}
    for session in sessions:
        session_dir = _resolve_session_dir(session)
        result = BattleReplayRunner().run(load_battle_packets(session_dir))
        reports[session] = build_damage_audit(result)

    report = reports[sessions[0]] if len(sessions) == 1 else build_multi_session_damage_audit(reports)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("=== Damage Prediction Audit ===")
    print(f"Session: {', '.join(sessions)}")
    print(f"Direct damage samples: {report['total_direct_damage']}")
    print(f"Matched predictions:    {report['matched_predictions']}")
    print(f"MAE: {report['mae']}  MAPE: {report['mape']}")
    print(f"Within 10%: {report['within_10pct']}  Within 25%: {report['within_25pct']}")
    if report.get("candidate_strategies"):
        print("Candidate strategies:")
        for name, item in report["candidate_strategies"].items():
            print(
                f"  {name}: n={item['samples']} "
                f"MAE={item['mae']} MAPE={item['mape']}"
            )
    if report.get("source_counts"):
        print("Runtime source counts:")
        for source_name, counts in report["source_counts"].items():
            summary = ", ".join(f"{k or '?'}={v}" for k, v in sorted(counts.items()))
            print(f"  {source_name}: {summary}")
    if len(sessions) > 1:
        print("Top skill groups:")
        for name, item in list(report["by_skill"].items())[:8]:
            print(
                f"  {name}: n={item['total']} matched={item['matched']} "
                f"MAE={item['mae']} MAPE={item['mape']}"
            )
    if report["catastrophic_high_confidence"]:
        print("High-confidence outliers:")
        for sample in report["catastrophic_high_confidence"]:
            print(
                f"  R{sample['round_num']} {sample['skill_name']}: "
                f"actual={sample['actual_total']} predicted={sample['predicted_total']}"
            )


if __name__ == "__main__":
    main()
