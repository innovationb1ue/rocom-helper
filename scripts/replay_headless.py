"""无头战斗回放 CLI — 纯后端运行，无需启动服务器或前端。

用法:
    py -m scripts.replay_headless [--session battle_session_1] [--round 7] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analysis.replay_runner import BattleReplayRunner


def _session_dir(name: str) -> Path:
    return Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "packets" / name


def _print_summary(result) -> None:
    print(f"=== Battle Replay Summary ===")
    print(f"Packets:   {result.total_packets}")
    print(f"Rounds:    {len(result.rounds)}")
    print(f"Result:    {result.battle_summary.get('result', '?')}")
    if result.stopped_early:
        print(f"(Stopped early at round {result.rounds[-1].round_num})")
    print()

    # Per-round damage predictions
    for rs in result.rounds:
        if not rs.damage_predictions:
            continue
        print(f"--- Round {rs.round_num} ---")
        opp = rs.state_at_end.get("opp_active")
        opp_name = opp.get("name", "?") if opp else "?"
        opp_hp = opp.get("current_hp", "?") if opp else "?"
        opp_max = opp.get("max_hp", "?") if opp else "?"
        print(f"  Target: {opp_name}  HP: {opp_hp}/{opp_max}")
        for pred in rs.damage_predictions:
            ko_mark = " [KO]" if pred.get("can_ko") else ""
            eff = pred.get("effectiveness_label", "") or ""
            name = pred.get("skill_name") or f"skill_{pred.get('skill_id', '?')}"
            exp_dmg = pred.get("expected_damage", "?")
            min_d = pred.get("min_damage", "?")
            max_d = pred.get("max_damage", "?")
            print(f"  {name:20s}  dmg: {exp_dmg!s:>5}  range: [{min_d!s}-{max_d!s}]  eff: {eff}{ko_mark}")
        print()

    # Hook advice
    all_hooks = []
    for ev in result.events:
        all_hooks.extend(ev.hook_advice)
    if all_hooks:
        print("=== Hook Advice ===")
        for ha in all_hooks:
            print(f"  [{ha['hook_id']}] {ha['title']}")
            for msg in ha.get("messages", []):
                print(f"    - {msg.get('message', '')}")
        print()

    # Final state
    fs = result.final_state
    print(f"=== Final State ===")
    print(f"Round: {fs.get('round')}  Result: {fs.get('result')}")
    print(f"My pets: {len(fs.get('my_pets', []))}  Opp pets: {len(fs.get('opp_pets', []))}")
    for p in fs.get("my_pets", []):
        status = "战败" if p.get("current_hp", 0) <= 0 else f"HP {p['current_hp']}/{p['max_hp']}"
        print(f"  {p.get('name', '?'):15s}  {status}")
    for p in fs.get("opp_pets", []):
        status = "战败" if p.get("current_hp", 0) <= 0 else f"HP {p['current_hp']}/{p['max_hp']}"
        print(f"  {p.get('name', '?'):15s}  {status}")


def main():
    parser = argparse.ArgumentParser(description="Headless battle replay (no server needed)")
    parser.add_argument("--session", default="battle_session_1", help="Session directory name")
    parser.add_argument("--round", type=int, default=None, help="Stop at this round")
    parser.add_argument("--json", action="store_true", help="Output full result as JSON")
    args = parser.parse_args()

    from tests.packet_reader import load_battle_packets

    session_path = _session_dir(args.session)
    if not session_path.exists():
        print(f"Session not found: {session_path}", file=sys.stderr)
        sys.exit(1)

    packets = load_battle_packets(session_path)
    if not packets:
        print("No battle packets found", file=sys.stderr)
        sys.exit(1)

    runner = BattleReplayRunner()
    result = runner.run(packets, stop_round=args.round)

    if args.json:
        output = {
            "total_packets": result.total_packets,
            "stopped_early": result.stopped_early,
            "rounds": [
                {
                    "round_num": rs.round_num,
                    "damage_predictions": rs.damage_predictions,
                    "battle_advice": rs.battle_advice,
                }
                for rs in result.rounds
            ],
            "final_state": result.final_state,
            "battle_summary": result.battle_summary,
        }
        json.dump(output, sys.stdout, default=str, ensure_ascii=False, indent=2)
    else:
        _print_summary(result)


if __name__ == "__main__":
    main()
