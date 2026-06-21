"""宠物/换宠相关 entry 格式化。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.formatting.core import FormattedEvent, is_mine, resolve_pet_name, side_label


def format_change_pet(entry: Dict[str, Any], state: Dict[str, Any]) -> FormattedEvent:
    battle_pet_id = entry.get("battle_pet_id")
    if battle_pet_id is not None:
        is_opp = int(battle_pet_id) >= 401
    else:
        is_opp = not is_mine(entry.get("actor_side"))
    side_str = "敌方" if is_opp else "我方"
    old_name = entry.get("_prev_active_name", "?")
    new_name = entry.get("new_pet_name") or entry.get("new_pet_id") or entry.get("battle_pet_id")
    if isinstance(new_name, int):
        new_name = resolve_pet_name(new_name, not is_opp, state)
    return FormattedEvent(
        kind="change_pet",
        round=0,
        summary=f"{side_str} 换宠: {old_name} → {new_name}",
        detail={"side": side_str, "old_name": old_name, "new_name": str(new_name)},
        icon="swap",
        color="cyan",
    )


def format_revive(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
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


def format_supply_pet(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    pets = entry.get("supply_pets", [])
    count = len(pets) if pets else 1
    return FormattedEvent(
        kind="reinforcement",
        round=0,
        summary=f"补宠: {count}只",
        detail={"supply_count": count, "raw_kind": "supply_pet"},
        icon="plus",
        color="cyan",
    )


def format_change_model(entry: Dict[str, Any], state: Dict[str, Any]) -> FormattedEvent:
    actor_side = entry.get("actor_side") or entry.get("pet_id")
    actor = side_label(actor_side)
    original = entry.get("original_pet_name")
    model = entry.get("model_pet_name")
    if original is None and actor_side is not None:
        original = resolve_pet_name(actor_side, is_mine(actor_side), state)

    if original and model and original != model:
        summary = f"模型变化: {actor} {original} -> {model}"
    elif model:
        summary = f"模型变化: {actor} -> {model}"
    else:
        summary = f"模型变化: {actor}"
    return FormattedEvent(
        kind="change_model",
        round=0,
        summary=summary,
        detail=entry,
        icon="skin",
        color="purple",
    )
