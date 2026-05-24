"""无头战斗回放 CLI — 纯后端运行，无需启动服务器或前端。

用法:
    py -m scripts.replay_headless [--session battle_session_1] [--round 7] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analysis.replay_runner import BattleReplayRunner

# Ensure UTF-8 output on Windows (Claude Code terminal)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


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

    # Per-round detail
    for rs in result.rounds:
        if rs.round_num == 0:
            continue
        has_content = rs.formatted_events or rs.damage_predictions or rs.suggestions
        if not has_content:
            continue

        print(f"--- Round {rs.round_num} ---")

        # Active pets
        for key, label in [("my_active", "My"), ("opp_active", "Opp")]:
            pet = rs.state_at_end.get(key) or rs.state_at_start.get(key)
            if pet:
                name = pet.get("name", "?")
                hp = pet.get("current_hp", 0)
                max_hp = pet.get("max_hp", 0)
                energy = pet.get("energy", 0)
                spd = pet.get("effective_speed") or pet.get("base_speed") or "?"
                base_spd = pet.get("base_speed")
                if spd != "?" and base_spd is not None and spd != base_spd:
                    spd = f"{spd} (base {base_spd})"
                print(f"  {label}: {name}  HP {hp}/{max_hp}  EP={energy}  SPD={spd}")

        # Formatted events
        if rs.formatted_events:
            for fe in rs.formatted_events:
                kind = fe.get("kind", "?")
                summary = fe.get("summary", "")
                print(f"  [{kind:20s}] {summary}")

        # Suggestions
        if rs.suggestions:
            for sug in rs.suggestions:
                print(f"  SUGGEST: [{sug.get('type', '?')}] {sug.get('message', '')}")

        # Damage predictions
        if rs.damage_predictions:
            for pred in rs.damage_predictions:
                ko_mark = " [KO]" if pred.get("can_ko") else ""
                eff = pred.get("effectiveness_label", "") or ""
                name = pred.get("skill_name") or f"skill_{pred.get('skill_id', '?')}"
                exp_dmg = pred.get("expected_damage", "?")
                min_d = pred.get("min_damage", "?")
                max_d = pred.get("max_damage", "?")
                print(f"  {name:20s}  dmg: {exp_dmg!s:>5}  range: [{min_d!s}-{max_d!s}]  eff: {eff}{ko_mark}")

        # Hook advice for this round
        for ev in rs.events:
            for ha in ev.hook_advice:
                print(f"  HOOK: [{ha.get('hook_id', '?')}] {ha.get('title', '')}")
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
    parser.add_argument("--json", "--no-json", default=True, action=argparse.BooleanOptionalAction, help="Write JSON result to tmp/ (default: --json, use --no-json to skip)")
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

    _print_summary(result)

    if args.json:
        output = {
            "total_packets": result.total_packets,
            "stopped_early": result.stopped_early,
            "rounds": [
                {
                    "round_num": rs.round_num,
                    "formatted_events": rs.formatted_events,
                    "suggestions": rs.suggestions,
                    "damage_predictions": rs.damage_predictions,
                    "battle_advice": rs.battle_advice,
                }
                for rs in result.rounds
            ],
            "final_state": result.final_state,
            "battle_summary": result.battle_summary,
        }
        tmp_dir = Path("tmp")
        tmp_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%H%M%S")
        out_path = tmp_dir / f"replay_{args.session}_{ts}.json"
        out_path.write_text(json.dumps(output, default=str, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON saved to: {out_path}")


if __name__ == "__main__":
    main()
