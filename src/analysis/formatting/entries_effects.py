"""战斗效果 entry 格式化。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.formatting.core import FormattedEvent, side_label
from src.data.loader import enrich_buff_modifiers


def format_effect_apply(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(entry.get("actor_side"))
    target = side_label(entry.get("target_side"))
    ename = entry.get("effect_name") or entry.get("effect_id") or "(未知效果)"
    stage = entry.get("effect_stage")
    related = entry.get("related_skills")
    modifier_summary = enrich_buff_modifiers({
        "id": entry.get("effect_id"),
        "name": ename,
        "stage": stage,
    }).get("modifier_summary", [])
    parts = [f"{actor}→{target} {ename}"]
    if modifier_summary:
        parts.append("/".join(modifier_summary))
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
            "modifier_summary": modifier_summary,
        },
        icon="experiment",
        color="purple",
    )


def format_effect_stage(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
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


def format_effect_link(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
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


def format_effect_trigger(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
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


def format_buff_trigger(entry: Dict[str, Any], _state: Dict[str, Any]) -> FormattedEvent:
    actor = side_label(entry.get("actor_side"))
    target = side_label(entry.get("target_side"))
    ename = entry.get("effect_name") or entry.get("buff_id") or entry.get("effect_id") or "(未知效果)"
    bases = entry.get("buffbase_ids") or []
    parts = [f"{actor}→{target} {ename}"]
    if bases:
        parts.append(f"base={','.join(str(x) for x in bases)}")
    return FormattedEvent(
        kind="buff_trigger",
        round=0,
        summary=f"效果触发: {' '.join(parts)}",
        detail=entry,
        icon="experiment",
        color="purple",
    )
