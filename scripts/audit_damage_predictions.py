"""回放伤害预测对账 CLI。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.analysis.damage_audit import (
    build_damage_audit,
    build_damage_calibration,
    build_multi_session_damage_audit,
    build_special_damage_rules,
)
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
    parser.add_argument(
        "--calibration-out",
        nargs="?",
        const="tmp/damage_calibration_suggested.json",
        help="Write suggested damage_calibration.json to this path",
    )
    parser.add_argument(
        "--special-rules-out",
        nargs="?",
        const="tmp/special_damage_rules_suggested.json",
        help="Write suggested special_damage_rules.json to this path",
    )
    args = parser.parse_args()

    sessions = args.sessions or [args.session]
    reports = {}
    for session in sessions:
        session_dir = _resolve_session_dir(session)
        result = BattleReplayRunner().run(load_battle_packets(session_dir))
        reports[session] = build_damage_audit(result)

    report = reports[sessions[0]] if len(sessions) == 1 else build_multi_session_damage_audit(reports)
    calibration = None
    if args.calibration_out:
        calibration = build_damage_calibration(report)
        out_path = Path(args.calibration_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(calibration, ensure_ascii=False, indent=2), encoding="utf-8")
    special_rules = None
    if args.special_rules_out:
        special_rules = build_special_damage_rules(report)
        out_path = Path(args.special_rules_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(special_rules, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        payload = dict(report)
        if calibration is not None:
            payload["calibration"] = calibration
        if special_rules is not None:
            payload["special_rules"] = special_rules
        print(json.dumps(payload, ensure_ascii=False, indent=2))
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
    zhui_da = (report.get("by_skill") or {}).get("追打")
    if zhui_da:
        applied = sum(
            1
            for sample in report.get("samples", [])
            if sample.get("skill_name") == "追打" and sample.get("server_power_applied")
        )
        print(
            "Server power pilot: "
            f"追打 applied={applied}/{zhui_da['matched']} "
            f"MAE={zhui_da['mae']} MAPE={zhui_da['mape']} "
            f"within25={zhui_da['within_25pct']}"
        )
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
    if args.calibration_out:
        print(f"Calibration suggestion written: {args.calibration_out}")
        print(f"Suggested skills: {len((calibration or {}).get('skills', {}))}")
    if args.special_rules_out:
        print(f"Special damage rules suggestion written: {args.special_rules_out}")
        print(f"Suggested special skills: {len((special_rules or {}).get('skills', {}))}")


if __name__ == "__main__":
    main()
