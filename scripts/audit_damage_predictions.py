"""回放伤害预测对账 CLI。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.analysis.damage_audit import build_damage_audit
from src.analysis.replay_runner import BattleReplayRunner
from tests.packet_reader import load_battle_packets


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit replay damage predictions")
    parser.add_argument("--session", default="battle_session_1")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    args = parser.parse_args()

    session_dir = Path("tests") / "fixtures" / "packets" / args.session
    result = BattleReplayRunner().run(load_battle_packets(session_dir))
    report = build_damage_audit(result)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("=== Damage Prediction Audit ===")
    print(f"Session: {args.session}")
    print(f"Direct damage samples: {report['total_direct_damage']}")
    print(f"Matched predictions:    {report['matched_predictions']}")
    print(f"MAE: {report['mae']}  MAPE: {report['mape']}")
    print(f"Within 10%: {report['within_10pct']}  Within 25%: {report['within_25pct']}")
    if report["catastrophic_high_confidence"]:
        print("High-confidence outliers:")
        for sample in report["catastrophic_high_confidence"]:
            print(
                f"  R{sample['round_num']} {sample['skill_name']}: "
                f"actual={sample['actual_total']} predicted={sample['predicted_total']}"
            )


if __name__ == "__main__":
    main()
