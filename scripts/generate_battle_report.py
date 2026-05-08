"""Generate a formatted battle report from captured packets.

Usage:
    python -m scripts.generate_battle_report [SESSION_DIR]

If SESSION_DIR is not provided, defaults to
tests/fixtures/packets/battle_session_1/.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    first_sub,
    side_name,
    buff_name,
    skill_name,
    normalize_skill_id,
    extract_state_wrappers_from_record,
)
from src.protocol.opcodes import summarize
from src.analysis.battle_state import BattleStateTracker
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


def _side_label(side: Optional[int]) -> str:
    if side is None:
        return "?"
    v = int(side)
    if v in (1, "我方"):
        return "我方"
    if v >= 401 or v in ("敌方",):
        return "敌方"
    if 1 <= v <= 6:
        return "我方"
    return f"side={v}"


def _format_entry(entry: Dict[str, Any]) -> str:
    """Format a single action entry for the report."""
    kind = entry.get("kind", "unknown")

    if kind == "skill_cast":
        actor = _side_label(entry.get("actor_side"))
        sname = entry.get("skill_name") or entry.get("skill_slot_index")
        if sname is None:
            sname = f"skill_id={entry.get('skill_id')}"
        ed = entry.get("energy_delta")
        ea = entry.get("energy_after")
        if ed is not None or ea is not None:
            return f"    ▸ 施放: {actor} 使用 {sname} (energy {ed}→{ea})"
        return f"    ▸ 施放: {actor} 使用 {sname}"

    if kind == "damage":
        target = _side_label(entry.get("damage_target_side") or entry.get("target_side"))
        dmg = entry.get("damage", 0)
        hp = entry.get("target_hp_after")
        sname = entry.get("skill_name")
        hp_str = f"HP→{hp}" if hp is not None else ""
        src = f" [{sname}]" if sname else ""
        return f"    ▸ 伤害: {target} 受到 {dmg} 伤害 ({hp_str}){src}"

    if kind == "defeat":
        winner = _side_label(entry.get("actor_side"))
        defeated = _side_label(entry.get("target_side"))
        return f"    ▸ 击败: {winner} 击败了 {defeated}!"

    if kind == "effect_apply":
        actor = _side_label(entry.get("actor_side"))
        target = _side_label(entry.get("target_side"))
        ename = entry.get("effect_name") or entry.get("effect_id")
        stage = entry.get("effect_stage")
        related = entry.get("related_skills")
        line = f"    ▸ 效果: {actor}→{target} {ename}"
        if stage is not None:
            line += f" stage={stage}"
        if related:
            names = [r.get("skill_name") or str(r.get("skill_id")) for r in related]
            line += f" 关联:{','.join(names)}"
        return line

    if kind == "effect_stage":
        actor = _side_label(entry.get("actor_side"))
        target = _side_label(entry.get("target_side"))
        ename = entry.get("effect_name") or entry.get("effect_id")
        base = entry.get("effect_base_name") or entry.get("effect_base")
        return f"    ▸ 效果阶段: {actor} {ename} base={base}"

    if kind == "effect_link":
        actor = _side_label(entry.get("actor_side"))
        target = _side_label(entry.get("target_side"))
        ename = entry.get("effect_name") or entry.get("effect_id")
        return f"    ▸ 效果链接: {actor}→{target} {ename}"

    if kind == "heal":
        actor = _side_label(entry.get("actor_side"))
        target = _side_label(entry.get("target_side"))
        heal_type = entry.get("heal_type")
        hp_after = entry.get("hp_after")
        line = f"    ▸ 治疗: {actor}→{target}"
        if hp_after is not None:
            line += f" HP→{hp_after}"
        if heal_type is not None:
            line += f" type={heal_type}"
        return line

    if kind == "energy":
        actor = _side_label(entry.get("actor_side"))
        target = _side_label(entry.get("target_side"))
        ed = entry.get("energy_delta")
        ea = entry.get("energy_after")
        line = f"    ▸ 能量: {actor}→{target}"
        if ed is not None:
            line += f" delta={ed}"
        if ea is not None:
            line += f" after={ea}"
        return line

    if kind == "effect_trigger":
        actor = _side_label(entry.get("actor_side"))
        target = _side_label(entry.get("target_side"))
        ename = entry.get("effect_name") or entry.get("effect_id")
        result = entry.get("trigger_result")
        params = entry.get("trigger_params")
        line = f"    ▸ 效果触发: {actor}→{target} {ename}"
        if result is not None:
            line += f" result={result}"
        if params:
            line += f" params={params}"
        return line

    if kind == "change_pet":
        battle_slot = entry.get("battle_pet_id")
        new_name = entry.get("new_pet_name") or entry.get("new_pet_id") or str(battle_slot)
        # Determine side from slot range: 401+ = opponent, 1-6 = player
        is_opp = battle_slot is not None and int(battle_slot) >= 401
        side = "敌方" if is_opp else "我方"
        # Rest pet = currently active pet for that side
        rest_name = "?"
        state = entry.get("_state")
        if state:
            active_key = "opp_active" if is_opp else "my_active"
            active = state.get(active_key)
            if active:
                rest_name = active.get("name", "?")
        return f"    ▸ 换宠: {side} {rest_name} → {new_name}"

    if kind == "ai_action":
        pet_id = entry.get("pet_id")
        ai_type = entry.get("ai_type")
        param = entry.get("param")
        return f"    ▸ AI行动: pet={pet_id} type={ai_type} param={param}"

    if kind == "pvp_perform_marker":
        uin = entry.get("uin")
        ptype = entry.get("pvp_type")
        return f"    ▸ PvP执行标记: uin={uin} type={ptype}"

    if kind == "data_update":
        uin = entry.get("uin")
        return f"    ▸ 数据更新: uin={uin}"

    if kind == "supply_pet":
        player_id = entry.get("player_id")
        pets = entry.get("supply_pets") or []
        return f"    ▸ 补给宠物: player={player_id} count={len(pets)}"

    if kind == "revive":
        actor = _side_label(entry.get("actor_side"))
        target = _side_label(entry.get("target_side"))
        return f"    ▸ 复活: {actor}→{target}"

    # Generic fallback for any other kind
    return f"    ▸ [{kind}] {entry}"


# ── main report generator ────────────────────────────────────────────────────


def generate_report(session_dir: Path) -> str:
    packets = load_battle_packets(session_dir)
    if not packets:
        return "No battle packets found."

    tracker = BattleStateTracker()
    lines: List[str] = []

    # Phase tracking
    current_round = 0
    phase_label = ""
    unknown_types: Dict[str, int] = {}

    for item in packets:
        record = item["record"]
        opcode = item["opcode"]

        kind, summary = summarize(record, None)
        detail = summary.get("detail", summary)
        if detail is None:
            detail = {}

        state = tracker.handle_event(opcode, detail)

        # ── battle enter ──
        if opcode == 0x1316:
            lines.append("=" * 72)
            lines.append("[对战开始] " + _format_battle_enter(detail))
            wrappers = detail.get("wrappers", [])
            my_pets = [w for w in wrappers if w.get("side") == 1 or (w.get("side") and 1 <= int(w.get("side")) <= 6)]
            opp_pets = [w for w in wrappers if w not in my_pets]
            all_init = opp_pets[:1] + my_pets
            lines.append(f"  初始精灵 ({len(all_init)} 只):")
            for w in all_init:
                sn = _side_label(w.get("side"))
                name = w.get("name", "?")
                hp = w.get("hp") or w.get("current_hp", 0)
                max_hp = w.get("max_hp", 0)
                energy = w.get("energy", "?")
                types = w.get("types", [])
                lines.append(f"    [{sn}] {name} hp={hp}/{max_hp} energy={energy} types={types}")

        # ── preplay ──
        elif opcode == 0x13F3:
            phase = detail.get("packet_phase", "?")
            lines.append(f"  ★ 战前预演 (phase={phase}):")
            for entry in detail.get("entries", []):
                lines.append(_format_entry(entry))
                _track_unknown(entry, unknown_types)

        # ── round start ──
        elif opcode == 0x131A:
            rnd = detail.get("round", 0)
            if rnd and rnd != current_round:
                current_round = rnd
                lines.append("")
                lines.append("─" * 72)
                lines.append(f"◆ 回合 {current_round} 开始")
            wrappers = detail.get("wrappers", [])
            for w in wrappers:
                sn = _side_label(w.get("side"))
                name = w.get("name", "?")
                hp = w.get("hp") or w.get("current_hp", 0)
                max_hp = w.get("max_hp", 0)
                energy = w.get("energy", "?")
                lines.append(f"    [{sn}] {name} hp={hp}/{max_hp} energy={energy}")

        # ── skill select (client) ──
        elif opcode == 0x130B:
            sid = detail.get("skill_id")
            slot = detail.get("skill_slot_index")
            cmd_flag = detail.get("cmd_flag")
            if sid:
                lines.append(f"  → 我方选择: skill_id={sid}")
            elif slot:
                lines.append(f"  → 我方选择: skill_slot={slot}")
            elif cmd_flag == 2:
                lines.append(f"  → 我方选择: 换人")
            else:
                lines.append(f"  → 我方选择: (等待服务端)")

        # ── skill declare (server) ──
        elif opcode == 0x1322:
            actor = _side_label(detail.get("actor_side"))
            sid = detail.get("skill_id")
            sname = detail.get("skill_name")
            slot = detail.get("skill_slot_index")
            if sname:
                lines.append(f"  → 服务端声明: {actor} 使用 {sname}")
            elif sid:
                lines.append(f"  → 服务端声明: {actor} 使用 skill_id={sid}")
            elif slot:
                lines.append(f"  → 服务端声明: {actor} 使用 slot={slot}")
            else:
                lines.append(f"  → 服务端声明: {actor} 使用 skill_id=None")

        # ── action resolve (0x1324) ──
        elif opcode == 0x1324:
            for entry in detail.get("entries", []):
                if entry.get("kind") == "change_pet":
                    entry["_state"] = state  # attach state for pet name lookup
                lines.append(_format_entry(entry))
                _track_unknown(entry, unknown_types)

        # ── action ack (0x130C) ──
        elif opcode == 0x130C:
            sname = detail.get("skill_name")
            action = detail.get("action_name")
            hp = detail.get("current_hp")
            energy = detail.get("energy_after")
            rc = detail.get("result_code")
            label = sname or action or "?"
            lines.append(f"  ✓ 确认: {label} hp={hp} energy={energy} result_code={rc}")

        # ── pvp perform (0x13FC) ──
        elif opcode == 0x13FC:
            phase = detail.get("packet_phase", "?")
            lines.append(f"  ★ PvP执行 (phase={phase}):")
            for entry in detail.get("entries", []):
                lines.append(_format_entry(entry))
                _track_unknown(entry, unknown_types)

        # ── battle finish ──
        elif opcode == 0x132C:
            lines.append("")
            lines.append("=" * 72)
            result = detail.get("result_name", "UNKNOWN")
            code = detail.get("result_code")
            rounds = detail.get("rounds")
            seconds = detail.get("seconds")
            pvp_score = detail.get("pvp_score")
            total_score = detail.get("total_pvp_score")
            max_score = detail.get("max_pvp_score")
            lines.append(f"[对战结束] result={result} code={code}")
            lines.append(f"  回合数={rounds} 时长={seconds}秒")
            lines.append(f"  PvP积分={pvp_score} 总分={total_score} 历史最高={max_score}")

    # ── final state summary ──
    final = tracker.get_state()
    lines.insert(0, "")
    lines.insert(0, _format_header(final))
    lines.append("")
    lines.append(_format_event_stats(final))

    # ── unknown types debug ──
    if unknown_types:
        lines.append("")
        lines.append("=" * 72)
        lines.append("未知类型统计 (DEBUG)")
        lines.append("=" * 72)
        for k, count in sorted(unknown_types.items(), key=lambda x: -x[1]):
            lines.append(f"  {k}: {count} 次")

    return "\n".join(lines)


def _format_battle_enter(detail: Dict[str, Any]) -> str:
    bid = detail.get("battle_id", "?")
    mode = detail.get("battle_mode", "?")
    max_round = detail.get("max_round", "?")
    return f"battle_id={bid} mode={mode} max_round={max_round}"


def _format_header(state: Dict[str, Any]) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("洛克王国 PvP 对战回放报告")
    lines.append("=" * 72)
    lines.append(f"  Battle ID : {state.get('battle_id')}")
    lines.append(f"  模式      : {state.get('battle_mode')}")
    lines.append(f"  结果      : {state.get('result')}")
    lines.append(f"  回合数    : {state.get('round')} / {state.get('max_round')}")
    lines.append(f"  天气      : {state.get('weather_id')}")
    lines.append("")
    lines.append("─" * 72)
    lines.append("我方阵容")
    lines.append("─" * 72)
    for p in state.get("my_pets", []):
        lines.append(_pet_line(p))
    lines.append("")
    lines.append("─" * 72)
    lines.append("敌方阵容")
    lines.append("─" * 72)
    for p in state.get("opp_pets", []):
        lines.append(_pet_line(p))
    return "\n".join(lines)


_OPCODE_KINDS = {
    0x1316: "battle_enter", 0x131A: "round_start", 0x130B: "client_skill_select",
    0x1322: "server_skill_declare", 0x1324: "action_resolve", 0x130C: "server_action_ack",
    0x132C: "battle_finish", 0x13F4: "special_refresh", 0x13FC: "pvp_perform",
    0x13F3: "preplay", 0x1312: "round_flow", 0x1313: "round_confirm",
    0x1314: "round_confirm_rsp",
}


def _format_event_stats(state: Dict[str, Any]) -> str:
    events = state.get("events", [])
    stats: Dict[str, int] = {}
    for e in events:
        opc = e.get("opcode", 0)
        kind_str = _OPCODE_KINDS.get(opc, hex(opc))
        stats[kind_str] = stats.get(kind_str, 0) + 1

    lines = []
    lines.append("=" * 72)
    lines.append("事件统计")
    lines.append("=" * 72)
    for kind_str, count in sorted(stats.items(), key=lambda x: -x[1]):
        lines.append(f"  {kind_str:<30s} {count:>3d} 次")
    lines.append(f"  {'总计':<30s} {len(events):>3d} 次")
    return "\n".join(lines)


def _track_unknown(entry: Dict[str, Any], unknown_types: Dict[str, int]) -> None:
    kind = entry.get("kind", "")
    if kind.startswith("unknown_type_"):
        unknown_types[kind] = unknown_types.get(kind, 0) + 1


# ── entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    session_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SESSION
    report = generate_report(session_dir)

    out_path = _PROJECT_ROOT / "docs" / "battle_session_1_report_new.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    sys.stdout.buffer.write((report + f"\n\nReport saved to: {out_path}\n").encode("utf-8", errors="replace"))
