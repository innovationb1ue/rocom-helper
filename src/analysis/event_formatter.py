"""战斗事件格式化模块 — 将原始协议事件转换为结构化显示数据。"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class FormattedEvent:
    kind: str
    round: int
    summary: str
    detail: Dict[str, Any]
    icon: str
    color: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def side_label(side: Optional[Any]) -> str:
    if side is None:
        return "?"
    v = int(side) if not isinstance(side, int) else side
    if v == 0:
        return "系统"
    if 1 <= v <= 6:
        return "我方"
    if v >= 401:
        return "敌方"
    return f"side={v}"


def _is_mine(side_value: Any) -> bool:
    if side_value is None:
        return False
    if isinstance(side_value, str):
        return side_value == "我方"
    v = int(side_value)
    return 1 <= v <= 6


def _resolve_pet_name(slot_or_id: Any, is_mine: bool, state: Dict[str, Any]) -> str:
    pet_list = state.get("my_pets", []) if is_mine else state.get("opp_pets", [])
    v = slot_or_id
    for pet in pet_list:
        if pet.get("slot") == v or pet.get("pet_id") == v:
            return pet.get("name", str(v))
    return str(v)


# ---------------------------------------------------------------------------
# Action entry formatters (from 0x1324 / 0x13FC / 0x13F3 entries)
# ---------------------------------------------------------------------------

def _fmt_skill_cast(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(entry.get("actor_side"))
    sname = entry.get("skill_name") or entry.get("skill_slot_index")
    if sname is None:
        sname = f"skill_id={entry.get('skill_id')}"
    ed = entry.get("energy_delta")
    ea = entry.get("energy_after")
    if ed is not None and ea is not None:
        if ed < 0:
            summary = f"{actor} 使用 {sname} (消耗{-ed}能量, 剩余{ea})"
        elif ed > 0:
            summary = f"{actor} 使用 {sname} (获得{ed}能量, 剩余{ea})"
        else:
            summary = f"{actor} 使用 {sname} (能量{ea})"
    elif ea is not None:
        summary = f"{actor} 使用 {sname} (能量{ea})"
    else:
        summary = f"{actor} 使用 {sname}"
    return FormattedEvent(
        kind="skill_cast",
        round=0,
        summary=summary,
        detail={
            "actor_side": actor,
            "skill_name": sname,
            "energy_delta": ed,
            "energy_after": ea,
        },
        icon="thunderbolt",
        color="blue",
    )


def _fmt_damage(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    target = side_label(entry.get("damage_target_side") or entry.get("target_side"))
    dmg = entry.get("damage", 0)
    hp = entry.get("target_hp_after")
    sname = entry.get("skill_name")
    hp_str = f"HP→{hp}" if hp is not None else ""
    src = f" [{sname}]" if sname else ""
    summary = f"{target} 受到 {dmg} 伤害 ({hp_str}){src}"
    return FormattedEvent(
        kind="damage",
        round=0,
        summary=summary,
        detail={
            "target_side": target,
            "damage": dmg,
            "hp_after": hp,
            "skill_name": sname,
        },
        icon="thunderbolt",
        color="red",
    )


def _fmt_defeat(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    winner = side_label(entry.get("actor_side"))
    defeated = side_label(entry.get("target_side"))
    return FormattedEvent(
        kind="defeat",
        round=0,
        summary=f"{winner} 击败了 {defeated}!",
        detail={"winner_side": winner, "defeated_side": defeated},
        icon="skull",
        color="red",
    )


def _fmt_effect_apply(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(entry.get("actor_side"))
    target = side_label(entry.get("target_side"))
    ename = entry.get("effect_name") or entry.get("effect_id") or "(未知效果)"
    stage = entry.get("effect_stage")
    related = entry.get("related_skills")
    parts = [f"{actor}→{target} {ename}"]
    if stage is not None:
        parts.append(f"stage={stage}")
    if related:
        names = [r.get("skill_name") or str(r.get("skill_id")) for r in related]
        parts.append(f"关联:{','.join(names)}")
    return FormattedEvent(
        kind="effect_apply",
        round=0,
        summary=f"效果: {' '.join(parts)}",
        detail={
            "actor_side": actor,
            "target_side": target,
            "effect_name": ename,
            "stage": stage,
        },
        icon="experiment",
        color="purple",
    )


def _fmt_effect_stage(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(entry.get("actor_side"))
    target = side_label(entry.get("target_side"))
    ename = entry.get("effect_name") or entry.get("effect_id") or "(未知效果)"
    base = entry.get("effect_base_name") or entry.get("effect_base")
    return FormattedEvent(
        kind="effect_stage",
        round=0,
        summary=f"效果阶段: {actor} {ename} base={base}",
        detail={"actor_side": actor, "target_side": target, "effect_name": ename, "effect_base": base},
        icon="experiment",
        color="purple",
    )


def _fmt_effect_link(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(entry.get("actor_side"))
    target = side_label(entry.get("target_side"))
    ename = entry.get("effect_name") or entry.get("effect_id") or "(未知效果)"
    return FormattedEvent(
        kind="effect_link",
        round=0,
        summary=f"效果链接: {actor}→{target} {ename}",
        detail={"actor_side": actor, "target_side": target, "effect_name": ename},
        icon="link",
        color="purple",
    )


def _fmt_heal(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(entry.get("actor_side"))
    target = side_label(entry.get("target_side"))
    hp_after = entry.get("hp_after") or entry.get("target_hp_after")
    heal_type = entry.get("heal_type")
    parts = [f"{actor}→{target}"]
    if hp_after is not None:
        parts.append(f"HP→{hp_after}")
    if heal_type is not None:
        parts.append(f"type={heal_type}")
    return FormattedEvent(
        kind="heal",
        round=0,
        summary=f"治疗: {' '.join(parts)}",
        detail={"actor_side": actor, "target_side": target, "hp_after": hp_after},
        icon="heart",
        color="green",
    )


def _fmt_energy(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(entry.get("actor_side"))
    target = side_label(entry.get("target_side"))
    ed = entry.get("energy_delta")
    ea = entry.get("energy_after")
    parts = [f"{actor}→{target}"]
    if ed is not None:
        parts.append(f"delta={ed}")
    if ea is not None:
        parts.append(f"after={ea}")
    return FormattedEvent(
        kind="energy",
        round=0,
        summary=f"能量: {' '.join(parts)}",
        detail={"actor_side": actor, "target_side": target, "energy_delta": ed, "energy_after": ea},
        icon="bolt",
        color="gold",
    )


def _fmt_change_pet(entry: Dict[str, Any], state: Dict[str, Any]) -> FormattedEvent:
    battle_pet_id = entry.get("battle_pet_id")
    if battle_pet_id is not None:
        is_opp = int(battle_pet_id) >= 401
    else:
        is_opp = not _is_mine(entry.get("actor_side"))
    side_str = "敌方" if is_opp else "我方"
    old_name = entry.get("_prev_active_name", "?")
    new_name = entry.get("new_pet_name") or entry.get("new_pet_id") or entry.get("battle_pet_id")
    if isinstance(new_name, int):
        new_name = _resolve_pet_name(new_name, not is_opp, state)
    return FormattedEvent(
        kind="change_pet",
        round=0,
        summary=f"{side_str} 换宠: {old_name} → {new_name}",
        detail={"side": side_str, "old_name": old_name, "new_name": str(new_name)},
        icon="swap",
        color="cyan",
    )


def _fmt_effect_trigger(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(entry.get("actor_side"))
    target = side_label(entry.get("target_side"))
    ename = entry.get("effect_name") or entry.get("effect_id") or "(未知效果)"
    result = entry.get("trigger_result")
    params = entry.get("trigger_params")
    parts = [f"{actor}→{target} {ename}"]
    if result is not None:
        parts.append(f"result={result}")
    if params:
        parts.append(f"params={params}")
    return FormattedEvent(
        kind="effect_trigger",
        round=0,
        summary=f"效果触发: {' '.join(parts)}",
        detail={"actor_side": actor, "target_side": target, "effect_name": ename},
        icon="experiment",
        color="purple",
    )


def _fmt_revive(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(entry.get("actor_side"))
    target = side_label(entry.get("target_side"))
    return FormattedEvent(
        kind="revive",
        round=0,
        summary=f"复活: {actor}→{target}",
        detail={"actor_side": actor, "target_side": target},
        icon="redo",
        color="green",
    )


def _fmt_ai_action(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    pet_id = entry.get("pet_id")
    ai_type = entry.get("ai_type")
    return FormattedEvent(
        kind="ai_action",
        round=0,
        summary=f"AI行动: pet={pet_id} type={ai_type}",
        detail={"pet_id": pet_id, "ai_type": ai_type},
        icon="robot",
        color="gray",
    )


def _fmt_pvp_perform_marker(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    pvp_type = entry.get("pvp_type", "?")
    return FormattedEvent(
        kind="pvp_perform_marker",
        round=0,
        summary=f"PVP演出 type={pvp_type}",
        detail={"pvp_type": pvp_type},
        icon="star",
        color="purple",
    )


def _fmt_supply_pet(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    pets = entry.get("supply_pets", [])
    count = len(pets) if pets else 1
    return FormattedEvent(
        kind="supply_pet",
        round=0,
        summary=f"补宠: {count}只",
        detail={"supply_count": count},
        icon="plus",
        color="cyan",
    )


def _fmt_generic(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    kind = entry.get("kind", "unknown")
    return FormattedEvent(
        kind=kind,
        round=0,
        summary=f"[{kind}]",
        detail=entry,
        icon="question",
        color="gray",
    )


_SUPPRESSED_KINDS = {"data_update"}

_ENTRY_FORMATTERS: Dict[str, Any] = {
    "skill_cast": _fmt_skill_cast,
    "damage": _fmt_damage,
    "defeat": _fmt_defeat,
    "effect_apply": _fmt_effect_apply,
    "effect_stage": _fmt_effect_stage,
    "effect_link": _fmt_effect_link,
    "heal": _fmt_heal,
    "energy": _fmt_energy,
    "change_pet": _fmt_change_pet,
    "effect_trigger": _fmt_effect_trigger,
    "revive": _fmt_revive,
    "ai_action": _fmt_ai_action,
    "pvp_perform_marker": _fmt_pvp_perform_marker,
    "supply_pet": _fmt_supply_pet,
}


def format_action_entry(entry: Dict[str, Any], state: Dict[str, Any], round_num: int = 0) -> Optional[FormattedEvent]:
    kind = entry.get("kind", "")
    if kind in _SUPPRESSED_KINDS:
        return None
    fmt = _ENTRY_FORMATTERS.get(kind, _fmt_generic)
    ev = fmt(entry, state)
    ev.round = round_num
    return ev


# ---------------------------------------------------------------------------
# Lifecycle event formatters
# ---------------------------------------------------------------------------

def format_battle_enter(detail: Dict[str, Any], state: Dict[str, Any]) -> FormattedEvent:
    bid = detail.get("battle_id", "?")
    mode = detail.get("battle_mode", "?")
    max_round = detail.get("max_round", "?")
    wrappers = detail.get("wrappers", [])
    my_team = []
    opp_team = []
    for w in wrappers:
        info = {
            "name": w.get("pet_name") or w.get("name", "?"),
            "hp": w.get("hp") or w.get("current_hp", 0),
            "max_hp": w.get("max_hp", 0),
            "types": w.get("types", []),
        }
        side = w.get("side")
        if _is_mine(side):
            my_team.append(info)
        else:
            opp_team.append(info)
    return FormattedEvent(
        kind="battle_enter",
        round=0,
        summary=f"对战开始 battle_id={bid} mode={mode} max_round={max_round}",
        detail={
            "battle_id": bid,
            "battle_mode": mode,
            "max_round": max_round,
            "my_team": my_team,
            "opp_team": opp_team,
        },
        icon="swords",
        color="green",
    )


def format_round_start(detail: Dict[str, Any], state: Dict[str, Any]) -> FormattedEvent:
    rnd = detail.get("round", 0)
    wrappers = detail.get("wrappers", [])
    pet_status = []
    for w in wrappers:
        pet_status.append({
            "side": side_label(w.get("side")),
            "name": w.get("name", "?"),
            "hp": w.get("hp") or w.get("current_hp", 0),
            "max_hp": w.get("max_hp", 0),
            "energy": w.get("energy", "?"),
        })
    return FormattedEvent(
        kind="round_start",
        round=rnd,
        summary=f"回合 {rnd} 开始",
        detail={"round": rnd, "pet_status": pet_status},
        icon="sync",
        color="blue",
    )


def format_battle_finish(detail: Dict[str, Any], state: Dict[str, Any]) -> FormattedEvent:
    result = detail.get("result_name", "UNKNOWN")
    rounds = detail.get("rounds")
    seconds = detail.get("seconds")
    pvp_score = detail.get("pvp_score")
    total_score = detail.get("total_pvp_score")
    max_score = detail.get("max_pvp_score")
    return FormattedEvent(
        kind="battle_finish",
        round=state.get("round", 0),
        summary=f"对战结束: {result} 回合={rounds} 时长={seconds}秒",
        detail={
            "result": result,
            "rounds": rounds,
            "seconds": seconds,
            "pvp_score": pvp_score,
            "total_pvp_score": total_score,
            "max_pvp_score": max_score,
        },
        icon="trophy" if result == "WIN" else "frown",
        color="green" if result == "WIN" else "red",
    )


def format_skill_select(detail: Dict[str, Any]) -> FormattedEvent:
    sid = detail.get("skill_id")
    slot = detail.get("skill_slot_index")
    cmd_flag = detail.get("cmd_flag")
    if sid:
        summary = f"我方选择: skill_id={sid}"
    elif slot:
        summary = f"我方选择: skill_slot={slot}"
    elif cmd_flag == 2:
        summary = "我方选择: 换人"
    else:
        summary = "我方选择: (等待服务端)"
    return FormattedEvent(
        kind="skill_select",
        round=0,
        summary=summary,
        detail={"skill_id": sid, "skill_slot_index": slot, "cmd_flag": cmd_flag},
        icon="select",
        color="geekblue",
    )


def format_skill_declare(detail: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(detail.get("actor_side"))
    sname = detail.get("skill_name")
    sid = detail.get("skill_id")
    slot = detail.get("skill_slot_index")
    if sname:
        summary = f"服务端声明: {actor} 使用 {sname}"
    elif sid:
        summary = f"服务端声明: {actor} 使用 skill_id={sid}"
    elif slot:
        summary = f"服务端声明: {actor} 使用 slot={slot}"
    elif actor == "?":
        summary = "服务端声明: (等待中)"
    else:
        summary = f"服务端声明: {actor}"
    return FormattedEvent(
        kind="skill_declare",
        round=0,
        summary=summary,
        detail={"actor_side": actor, "skill_name": sname, "skill_id": sid},
        icon="sound",
        color="geekblue",
    )


def format_action_ack(detail: Dict[str, Any]) -> FormattedEvent:
    sname = detail.get("skill_name")
    action = detail.get("action_name")
    hp = detail.get("current_hp")
    energy = detail.get("energy_after")
    rc = detail.get("result_code")
    label = sname or action or "?"
    return FormattedEvent(
        kind="action_ack",
        round=0,
        summary=f"确认: {label} HP={hp} 能量={energy} result={rc}",
        detail={"label": label, "current_hp": hp, "energy_after": energy, "result_code": rc},
        icon="check",
        color="blue",
    )


def format_special_refresh(detail: Dict[str, Any]) -> FormattedEvent:
    action = detail.get("action_name", "")
    energy_delta = detail.get("energy_delta")
    energy_after = detail.get("energy_after")
    skill_options = detail.get("skill_options", [])
    if action:
        summary = f"{action} (能量 {energy_delta}→{energy_after})"
    elif skill_options:
        names = [s.get("skill_name", "?") for s in skill_options[:4]]
        summary = f"技能选项: {', '.join(names)}"
    else:
        summary = "特殊刷新"
    return FormattedEvent(
        kind="special_refresh",
        round=0,
        summary=summary,
        detail={"action_name": action, "energy_delta": energy_delta, "energy_after": energy_after},
        icon="reload",
        color="gold",
    )


def format_round_flow(detail: Dict[str, Any]) -> FormattedEvent:
    rnd = detail.get("round")
    return FormattedEvent(
        kind="round_flow",
        round=rnd or 0,
        summary=f"回合流 round={rnd}",
        detail={"round": rnd},
        icon="sync",
        color="blue",
    )


# ---------------------------------------------------------------------------
# Multi-hit damage merge
# ---------------------------------------------------------------------------


def _merge_damage_events(events: List[FormattedEvent]) -> List[FormattedEvent]:
    """Merge consecutive identical damage events into a single event with a count."""
    if not events:
        return events
    result: List[FormattedEvent] = []
    i = 0
    while i < len(events):
        ev = events[i]
        if ev.kind != "damage":
            result.append(ev)
            i += 1
            continue
        count = 1
        j = i + 1
        while j < len(events):
            nxt = events[j]
            if nxt.kind != "damage":
                break
            if (nxt.detail.get("target_side") == ev.detail.get("target_side")
                    and nxt.detail.get("damage") == ev.detail.get("damage")
                    and nxt.detail.get("skill_name") == ev.detail.get("skill_name")):
                count += 1
                j += 1
            else:
                break
        if count > 1:
            last = events[j - 1]
            hp = last.detail.get("hp_after")
            dmg = ev.detail.get("damage", 0)
            target = ev.detail.get("target_side", "")
            skill = ev.detail.get("skill_name")
            hp_str = f"HP→{hp}" if hp is not None else ""
            src = f" [{skill}]" if skill else ""
            merged = FormattedEvent(
                kind="damage",
                round=ev.round,
                summary=f"{target} 受到 {dmg}x{count} 伤害 ({hp_str}){src}",
                detail={**ev.detail, "hit_count": count, "hp_after": last.detail.get("hp_after")},
                icon=ev.icon,
                color=ev.color,
            )
            result.append(merged)
        else:
            result.append(ev)
        i = j
    return result


# ---------------------------------------------------------------------------
# Top-level dispatch
# ---------------------------------------------------------------------------

def format_battle_event(
    opcode: int,
    detail: Dict[str, Any],
    state: Dict[str, Any],
    round_num: int = 0,
) -> List[FormattedEvent]:
    """Format a single protocol event into one or more FormattedEvents."""
    events: List[FormattedEvent] = []

    if opcode == 0x1316:
        ev = format_battle_enter(detail, state)
        ev.round = round_num
        events.append(ev)

    elif opcode == 0x131A:
        ev = format_round_start(detail, state)
        events.append(ev)

    elif opcode == 0x132C:
        ev = format_battle_finish(detail, state)
        events.append(ev)

    elif opcode == 0x130B:
        ev = format_skill_select(detail)
        ev.round = round_num
        events.append(ev)

    elif opcode == 0x1322:
        ev = format_skill_declare(detail)
        ev.round = round_num
        events.append(ev)

    elif opcode == 0x130C:
        ev = format_action_ack(detail)
        ev.round = round_num
        events.append(ev)

    elif opcode == 0x13F4:
        ev = format_special_refresh(detail)
        ev.round = round_num
        events.append(ev)

    elif opcode == 0x1312:
        ev = format_round_flow(detail)
        events.append(ev)

    elif opcode in (0x1324, 0x13FC, 0x13F3):
        for entry in detail.get("entries", []):
            ev = format_action_entry(entry, state, round_num)
            if ev is not None:
                events.append(ev)
        events = _merge_damage_events(events)

    return events


# ---------------------------------------------------------------------------
# Battle summary computation
# ---------------------------------------------------------------------------

def compute_battle_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    my_pets_final = []
    for p in state.get("my_pets", []):
        my_pets_final.append({
            "name": p.get("name", "?"),
            "hp": p.get("current_hp", 0),
            "max_hp": p.get("max_hp", 0),
            "status": "战败" if p.get("current_hp", 0) <= 0 else "存活",
        })
    opp_pets_final = []
    for p in state.get("opp_pets", []):
        opp_pets_final.append({
            "name": p.get("name", "?"),
            "hp": p.get("current_hp", 0),
            "max_hp": p.get("max_hp", 0),
            "status": "战败" if p.get("current_hp", 0) <= 0 else "存活",
        })

    raw_events = state.get("events", [])
    event_stats: Dict[str, int] = {}
    for e in raw_events:
        opc = e.get("opcode", 0)
        key = _OPCODE_LABELS.get(opc, hex(opc))
        event_stats[key] = event_stats.get(key, 0) + 1

    return {
        "result": state.get("result"),
        "rounds": state.get("round"),
        "my_pets_final": my_pets_final,
        "opp_pets_final": opp_pets_final,
        "event_stats": event_stats,
    }


_OPCODE_LABELS = {
    0x1316: "battle_enter", 0x131A: "round_start", 0x130B: "client_skill_select",
    0x1322: "server_skill_declare", 0x1324: "action_resolve", 0x130C: "server_action_ack",
    0x132C: "battle_finish", 0x13F4: "special_refresh", 0x13FC: "pvp_perform",
    0x13F3: "preplay", 0x1312: "round_flow",
}
