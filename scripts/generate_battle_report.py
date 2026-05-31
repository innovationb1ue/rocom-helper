"""Generate a formatted battle report from captured packets.

Usage:
    py -m scripts.generate_battle_report [SESSION_DIR]

If SESSION_DIR is not provided, defaults to
tests/fixtures/packets/battle_session_1/.

Options:
    --round N   Stop at round N
    --json      Output full result as JSON
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure UTF-8 output on Windows (Claude Code terminal)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.packet_reader import load_battle_packets

DEFAULT_SESSION = _PROJECT_ROOT / "tests" / "fixtures" / "packets" / "battle_session_1"


# ── helpers ──────────────────────────────────────────────────────────────────


def _bar(pct: float, width: int = 20) -> str:
    filled = max(0, min(width, int(pct * width)))
    return "#" * filled + "-" * (width - filled)


def _pet_line(pet: Dict[str, Any]) -> str:
    name = pet.get("name", "?")
    pid = pet.get("pet_id", 0)
    types = pet.get("types", [])
    hp = pet.get("current_hp", 0)
    max_hp = pet.get("max_hp", 0)
    energy = pet.get("energy", 0)
    level = pet.get("level", 0)
    pct = hp / max_hp if max_hp > 0 else 1.0
    status = "战败" if hp <= 0 else "存活"
    return (
        f"  {name:<10s} id={pid:<10d} 属性={types} "
        f"HP={hp:>3d}/{max_hp} 能量={energy:>2d} Lv.{level} "
        f"{status} [{_bar(pct)}] {int(pct * 100)}%"
    )


_OPCODE_KINDS = {
    0x1316: "battle_enter", 0x131A: "round_start", 0x130B: "client_skill_select",
    0x1322: "server_skill_declare", 0x1324: "action_resolve", 0x130C: "server_action_ack",
    0x132C: "battle_finish", 0x13F4: "special_refresh", 0x13FC: "pvp_perform",
    0x13F3: "preplay", 0x1312: "round_flow", 0x1313: "round_confirm",
    0x1314: "round_confirm_rsp",
}


# ── report generator ────────────────────────────────────────────────────────


def generate_report(session_dir: Path, stop_round: Optional[int] = None) -> str:
    """Generate a complete battle report using the full replay pipeline."""
    from src.analysis.replay_runner import BattleReplayRunner

    packets = load_battle_packets(session_dir)
    if not packets:
        return "No battle packets found."

    runner = BattleReplayRunner()
    result = runner.run(packets, stop_round=stop_round)
    return generate_report_from_result(result)


def generate_report_from_result(result: Any) -> str:
    """Render a battle report from an existing ReplayResult."""
    lines: List[str] = []

    # ── header ──
    lines.append("=" * 72)
    lines.append("洛克王国 PvP 对战回放报告")
    lines.append("=" * 72)
    fs = result.final_state
    lines.append(f"  Battle ID : {fs.get('battle_id')}")
    lines.append(f"  模式      : {fs.get('battle_mode')}")
    lines.append(f"  结果      : {result.battle_summary.get('result', '?')}")
    lines.append(f"  回合数    : {fs.get('round')} / {fs.get('max_round')}")
    lines.append(f"  数据包    : {result.total_packets}")
    lines.append(f"  天气      : {fs.get('weather_id')}")
    if result.stopped_early:
        lines.append(f"  (提前停止于回合 {result.rounds[-1].round_num})")
    lines.append("")
    lines.append("─" * 72)
    lines.append("我方阵容")
    lines.append("─" * 72)
    for p in fs.get("my_pets", []):
        lines.append(_pet_line(p))
    lines.append("")
    lines.append("─" * 72)
    lines.append("敌方阵容")
    lines.append("─" * 72)
    for p in fs.get("opp_pets", []):
        lines.append(_pet_line(p))

    # ── per-round detail ──
    for rs in result.rounds:
        if rs.round_num == 0:
            continue
        lines.append("")
        lines.append("═" * 72)
        lines.append(f"◆ 回合 {rs.round_num}")
        lines.append("═" * 72)

        # Active pets status at start of round
        for key, label in [("my_active", "我方"), ("opp_active", "敌方")]:
            pet = rs.state_at_start.get(key) or rs.state_at_end.get(key)
            if pet:
                name = pet.get("name", "?")
                hp = pet.get("current_hp", 0)
                max_hp = pet.get("max_hp", 0)
                energy = pet.get("energy", 0)
                hp_str = f"HP {hp}/{max_hp}" if max_hp > 0 else f"HP {hp}"
                spd = pet.get("effective_speed") or pet.get("base_speed")
                base_spd = pet.get("base_speed")
                if spd is not None:
                    spd_str = f"  速度={spd}" if spd == base_spd or base_spd is None else f"  速度={spd}(base {base_spd})"
                else:
                    spd_str = ""
                lines.append(f"  {label}: {name}  {hp_str}  能量={energy}{spd_str}")

        # Formatted events
        if rs.formatted_events:
            lines.append("")
            lines.append("  事件:")
            for fe in rs.formatted_events:
                kind = fe.get("kind", "?")
                summary = fe.get("summary", "")
                icon = fe.get("icon", "")
                color = fe.get("color", "")
                lines.append(f"    [{kind:20s}] {summary}")

        # Suggestions
        if rs.suggestions:
            lines.append("")
            lines.append("  建议:")
            for sug in rs.suggestions:
                stype = sug.get("type", "?")
                msg = sug.get("message", "")
                lines.append(f"    ⚡ [{stype}] {msg}")

        # Damage predictions
        if rs.damage_predictions:
            lines.append("")
            lines.append("  伤害预测:")
            opp = rs.state_at_end.get("opp_active") or rs.state_at_start.get("opp_active")
            if opp:
                opp_name = opp.get("name", "?")
                opp_hp = opp.get("current_hp", "?")
                opp_max = opp.get("max_hp", "?")
                lines.append(f"    目标: {opp_name}  HP: {opp_hp}/{opp_max}")
            for pred in rs.damage_predictions:
                name = pred.get("skill_name") or f"skill_{pred.get('skill_id', '?')}"
                exp_dmg = pred.get("expected_damage")
                ko_mark = " ★KO" if pred.get("can_ko") else ""
                eff = pred.get("effectiveness_label", "") or ""
                min_d = pred.get("min_damage", "-")
                max_d = pred.get("max_damage", "-")
                energy_cost = pred.get("energy_cost", "")
                hit_count = pred.get("hit_count", 1)
                lines.append(
                    f"    {name:20s}  dmg: {exp_dmg!s:>5}  "
                    f"range: [{min_d!s}-{max_d!s}]  eff: {eff}{ko_mark}"
                )
                # Damage breakdown
                bd = pred.get("damage_breakdown")
                if bd:
                    parts = []
                    for bk, bv in [
                        ("power", bd.get("effective_power")),
                        ("ability", bd.get("ability_level")),
                        ("atk", bd.get("atk")),
                        ("def", bd.get("def_")),
                        ("eff", bd.get("effectiveness")),
                        ("stab", bd.get("stab")),
                        ("weather", bd.get("weather_mult")),
                        ("hits", bd.get("hit_count", hit_count)),
                    ]:
                        if bv is not None:
                            parts.append(f"{bk}={bv}")
                    if parts:
                        lines.append(f"      {' '.join(parts)}")
                # Warnings
                for w in pred.get("warnings", []):
                    lines.append(f"      ⚠ {w}")

        if rs.opp_skill_analysis:
            lines.append("")
            lines.append(f"  对手技能分析 (source={rs.opp_skill_source or 'unknown'}):")
            for pred in rs.opp_skill_analysis:
                name = pred.get("skill_name") or f"skill_{pred.get('skill_id', '?')}"
                exp_dmg = pred.get("expected_damage")
                ko_mark = " ★KO" if pred.get("can_ko") else ""
                eff = pred.get("effectiveness_label", "") or ""
                lines.append(
                    f"    {name:20s}  dmg: {exp_dmg!s:>5}  "
                    f"eff: {eff}{ko_mark}"
                )

        if rs.tactical_recommendations:
            lines.append("")
            rec = rs.tactical_recommendations
            lines.append(f"  战术推荐 ({rec.get('confidence', '?')}):")
            for action in rec.get("actions", [])[:5]:
                label = action.get("skill_name") or action.get("switch_to_name") or action.get("action_type")
                lines.append(
                    f"    {label}: {action.get('reason', '')} score={action.get('score')}"
                )

        # Hook advice for this round
        round_hooks = []
        for ev in rs.events:
            round_hooks.extend(ev.hook_advice)
        if round_hooks:
            lines.append("")
            lines.append("  Hook 建议:")
            for ha in round_hooks:
                hook_id = ha.get("hook_id", "?")
                title = ha.get("title", "")
                priority = ha.get("priority", 2)
                pri_label = ["紧急", "重要", "提示"][min(priority, 2)]
                lines.append(f"    [{hook_id}] ({pri_label}) {title}")
                for msg in ha.get("messages", []):
                    lines.append(f"      - {msg.get('message', '')}")

    # ── battle summary ──
    summary = result.battle_summary
    lines.append("")
    lines.append("═" * 72)
    lines.append("对战结算")
    lines.append("═" * 72)
    result_name = summary.get("result", "?")
    rounds = summary.get("rounds", "?")
    lines.append(f"  结果: {result_name}  回合数: {rounds}")

    for label, key in [("我方", "my_pets_final"), ("敌方", "opp_pets_final")]:
        lines.append(f"  {label}:")
        for p in summary.get(key, []):
            name = p.get("name", "?")
            hp = p.get("hp", 0)
            max_hp = p.get("max_hp", 1)
            status = "战败" if hp <= 0 else f"HP {hp}/{max_hp}"
            lines.append(f"    {name:15s}  {status}")

    # ── event stats ──
    event_stats = summary.get("event_stats", {})
    if event_stats:
        lines.append("")
        lines.append("=" * 72)
        lines.append("事件统计")
        lines.append("=" * 72)
        total = 0
        for kind_str, count in sorted(event_stats.items(), key=lambda x: -x[1]):
            lines.append(f"  {kind_str:<30s} {count:>3d} 次")
            total += count
        lines.append(f"  {'总计':<30s} {total:>3d} 次")

    # ── all hook advice summary ──
    all_hooks = []
    for ev in result.events:
        all_hooks.extend(ev.hook_advice)
    if all_hooks:
        lines.append("")
        lines.append("═" * 72)
        lines.append("全部 Hook 建议")
        lines.append("═" * 72)
        for ha in all_hooks:
            lines.append(f"  [{ha.get('hook_id', '?')}] {ha.get('title', '')}")
            for msg in ha.get("messages", []):
                lines.append(f"    - {msg.get('message', '')}")

    return "\n".join(lines)


def replay_result_to_dict(result: Any) -> Dict[str, Any]:
    """Serialize ReplayResult to the JSON shape used by local report tools."""
    return {
        "total_packets": result.total_packets,
        "stopped_early": result.stopped_early,
        "rounds": [
            {
                "round_num": rs.round_num,
                "formatted_events": rs.formatted_events,
                "suggestions": rs.suggestions,
                "damage_predictions": rs.damage_predictions,
                "battle_advice": rs.battle_advice,
                "traits": rs.traits,
                "opp_traits": rs.opp_traits,
                "opp_skill_analysis": rs.opp_skill_analysis,
                "opp_skill_source": rs.opp_skill_source,
                "tactical_recommendations": rs.tactical_recommendations,
                "messages": rs.messages,
            }
            for rs in result.rounds
        ],
        "events": [
            {
                "index": ev.index,
                "opcode": ev.opcode,
                "kind": ev.kind,
                "round_num": ev.round_num,
                "formatted_events": ev.formatted_events,
                "battle_advice": ev.battle_advice,
                "hook_advice": ev.hook_advice,
                "suggestions": ev.suggestions,
                "tactical": ev.tactical,
                "messages": ev.messages,
            }
            for ev in result.events
        ],
        "final_state": result.final_state,
        "battle_summary": result.battle_summary,
        "messages": result.messages,
    }


# ── entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import json as _json

    from src.analysis.replay_runner import BattleReplayRunner

    parser = argparse.ArgumentParser(description="Battle report generator")
    parser.add_argument("session_dir", nargs="?", default=None, help="Session directory path")
    parser.add_argument("--round", type=int, default=None, help="Stop at this round")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    session_dir = Path(args.session_dir) if args.session_dir else DEFAULT_SESSION

    pkts = load_battle_packets(session_dir)
    if not pkts:
        print("No battle packets found.", file=sys.stderr)
        sys.exit(1)

    runner = BattleReplayRunner()
    result = runner.run(pkts, stop_round=args.round)

    if args.json:
        output = replay_result_to_dict(result)
        sys.stdout.buffer.write(
            _json.dumps(output, default=str, ensure_ascii=False, indent=2).encode("utf-8")
        )
    else:
        report = generate_report(session_dir, stop_round=args.round)
        out_path = _PROJECT_ROOT / "docs" / "battle_report.txt"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        sys.stdout.buffer.write(
            (report + f"\n\nReport saved to: {out_path}\n").encode("utf-8", errors="replace")
        )
