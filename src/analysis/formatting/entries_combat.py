"""战斗动作 entry 格式化：技能、伤害、击败。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.formatting.core import FormattedEvent, resolve_pet_display_name, side_label


def format_skill_cast(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
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


def format_damage(entry: Dict[str, Any], state: Dict[str, Any]) -> FormattedEvent:
    target_side = entry.get("damage_target_side") or entry.get("target_side")
    target_side_label = side_label(target_side)
    target_name = resolve_pet_display_name(target_side, state, pet_id=entry.get("target_pet_id"))
    target = _side_with_pet_name(target_side_label, target_name)
    dmg = entry.get("damage", 0)
    hp = entry.get("hp_after")
    if hp is None:
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
            "target_side": target_side_label,
            "target_name": target_name,
            "damage": dmg,
            "hp_after": hp,
            "hp_before": entry.get("hp_before"),
            "ledger_id": entry.get("ledger_id"),
            "actual_damage": entry.get("actual_damage"),
            "damage_result": entry.get("damage_result"),
            "target_pet_id": entry.get("target_pet_id"),
            "skill_name": sname,
        },
        icon="thunderbolt",
        color="red",
    )


def format_defeat(entry: Dict[str, Any], state: Dict[str, Any]) -> FormattedEvent:
    winner = side_label(entry.get("actor_side"))
    defeated_side = entry.get("target_side")
    defeated_side_label = side_label(defeated_side)
    defeated = resolve_pet_display_name(
        defeated_side,
        state,
        pet_id=entry.get("target_pet_id"),
    )

    return FormattedEvent(
        kind="defeat",
        round=0,
        summary=f"{winner} 击败了 {defeated}!",
        detail={
            "winner_side": winner,
            "defeated_side": defeated_side_label,
            "defeated_name": defeated,
            "target_pet_id": entry.get("target_pet_id"),
        },
        icon="skull",
        color="red",
    )


def _side_with_pet_name(side: str, pet_name: str) -> str:
    if pet_name == side or pet_name in {"?", ""}:
        return side
    return f"{side}({pet_name})"
