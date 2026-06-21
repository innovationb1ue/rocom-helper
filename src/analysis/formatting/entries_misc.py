"""其余战斗 entry 格式化。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.formatting.core import FormattedEvent, side_label


def format_ai_action(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
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


def format_pvp_perform_marker(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    pvp_type = entry.get("pvp_type", "?")
    return FormattedEvent(
        kind="pvp_perform",
        round=0,
        summary=f"PVP演出 type={pvp_type}",
        detail={"pvp_type": pvp_type, "raw_kind": "pvp_perform_marker"},
        icon="star",
        color="purple",
    )


def format_generic(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    kind = entry.get("kind", "unknown")
    return FormattedEvent(
        kind=kind,
        round=0,
        summary=f"[{kind}]",
        detail=entry,
        icon="question",
        color="gray",
    )


def format_weather_change(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    name = entry.get("weather_name") or entry.get("weather_id", "?")
    expire = entry.get("expire_round")
    skill = entry.get("skill_name")
    parts = [f"天气变化: {name}"]
    if expire is not None:
        parts.append(f"持续至回合{expire}")
    if skill:
        parts.append(f"({skill})")
    return FormattedEvent(
        kind="weather_change",
        round=0,
        summary=" ".join(parts),
        detail=entry,
        icon="cloud-sun",
        color="blue",
    )


def format_skill_state(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    code = entry.get("state_code", "?")
    return FormattedEvent(
        kind="skill_state",
        round=0,
        summary=f"技能状态变化: code={code}",
        detail=entry,
        icon="settings",
        color="gray",
    )


def format_role_skill_cast(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    name = entry.get("skill_name") or entry.get("skill_id", "?")
    ok = entry.get("is_call_success")
    summary = f"天命技能: {name}"
    if ok is not None:
        summary += f" {'成功' if ok else '失败'}"
    return FormattedEvent(
        kind="role_skill_cast",
        round=0,
        summary=summary,
        detail=entry,
        icon="star",
        color="purple",
    )


def format_special_move(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    name = entry.get("skill_name") or entry.get("special_move_id", "?")
    return FormattedEvent(
        kind="special_move",
        round=0,
        summary=f"特殊行动: {name}",
        detail=entry,
        icon="zap",
        color="orange",
    )


def format_skill_pos_change(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    infos = entry.get("skill_pos_infos", [])
    n = len(infos)
    return FormattedEvent(
        kind="skill_pos_change",
        round=0,
        summary=f"技能位置变化: {n}个技能",
        detail=entry,
        icon="move",
        color="gray",
    )


def format_idle(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    return FormattedEvent(
        kind="idle",
        round=0,
        summary="待机",
        detail=entry,
        icon="pause",
        color="gray",
    )


def format_notify_perform(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    t = entry.get("notify_type", "?")
    return FormattedEvent(
        kind="notify_perform",
        round=0,
        summary=f"通知: type={t}",
        detail=entry,
        icon="bell",
        color="gray",
    )


def format_cmd_failed(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    reason = entry.get("failed_reason", "?")
    return FormattedEvent(
        kind="cmd_failed",
        round=0,
        summary=f"指令失败: reason={reason}",
        detail=entry,
        icon="alert-circle",
        color="red",
    )


def format_runaway(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(entry.get("actor_side"))
    return FormattedEvent(
        kind="runaway",
        round=0,
        summary=f"逃跑: {actor}",
        detail=entry,
        icon="log-out",
        color="orange",
    )
