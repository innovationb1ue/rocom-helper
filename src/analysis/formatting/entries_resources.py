"""战斗资源 entry 格式化：HP、能量、道具。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.formatting.core import FormattedEvent, side_label


def format_heal(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
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


def format_energy(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
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


def format_sp_energy_change(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    t = entry.get("sp_change_type", "?")
    val = entry.get("change_value", 0)
    return FormattedEvent(
        kind="sp_energy_change",
        round=0,
        summary=f"SP能量: type={t} value={val}",
        detail=entry,
        icon="battery",
        color="yellow",
    )


def format_sp_energy_trigger(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    old = entry.get("old_skill_name") or entry.get("old_skill_id", "?")
    new = entry.get("new_skill_name") or entry.get("new_skill_id", "?")
    return FormattedEvent(
        kind="sp_energy_trigger",
        round=0,
        summary=f"SP触发: {old} → {new}",
        detail=entry,
        icon="refresh-cw",
        color="yellow",
    )


def format_use_item(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    item = entry.get("item_id", "?")
    target = side_label(entry.get("target_id"))
    return FormattedEvent(
        kind="use_item",
        round=0,
        summary=f"使用道具: item={item} target={target}",
        detail=entry,
        icon="package",
        color="gold",
    )
