"""生命周期和命令 opcode 的事件格式化。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.formatting.core import FormattedEvent, is_mine, side_label


def format_battle_enter(detail: Dict[str, Any], state: Dict[str, Any]) -> FormattedEvent:
    bid = detail.get("battle_id", "?")
    mode = detail.get("battle_mode", "?")
    max_round = detail.get("max_round", "?")
    wrappers = detail.get("wrappers", [])
    my_team = []
    opp_team = []
    for wrapper in wrappers:
        info = {
            "name": wrapper.get("pet_name") or wrapper.get("name", "?"),
            "hp": wrapper.get("hp") or wrapper.get("current_hp", 0),
            "max_hp": wrapper.get("max_hp", 0),
            "types": wrapper.get("types", []),
        }
        side = wrapper.get("side")
        if is_mine(side):
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
    for wrapper in wrappers:
        pet_status.append({
            "side": side_label(wrapper.get("side")),
            "name": wrapper.get("name", "?"),
            "hp": wrapper.get("hp") or wrapper.get("current_hp", 0),
            "max_hp": wrapper.get("max_hp", 0),
            "energy": wrapper.get("energy", "?"),
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
        names = [skill.get("skill_name", "?") for skill in skill_options[:4]]
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
