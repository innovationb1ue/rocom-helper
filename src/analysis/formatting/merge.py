"""格式化事件后处理。"""
from __future__ import annotations

from typing import List

from src.analysis.formatting.core import FormattedEvent


def merge_damage_events(events: List[FormattedEvent]) -> List[FormattedEvent]:
    """Merge consecutive identical damage events into a single event with a count."""
    if not events:
        return events
    result: List[FormattedEvent] = []
    i = 0
    while i < len(events):
        event = events[i]
        if event.kind != "damage":
            result.append(event)
            i += 1
            continue

        count = 1
        j = i + 1
        while j < len(events):
            nxt = events[j]
            if nxt.kind != "damage":
                break
            if (
                nxt.detail.get("target_side") == event.detail.get("target_side")
                and nxt.detail.get("damage") == event.detail.get("damage")
                and nxt.detail.get("skill_name") == event.detail.get("skill_name")
            ):
                count += 1
                j += 1
            else:
                break

        if count > 1:
            last = events[j - 1]
            hp = last.detail.get("hp_after")
            damage = event.detail.get("damage", 0)
            target = _target_display(event.detail)
            skill = event.detail.get("skill_name")
            ledger_ids = [
                item.detail.get("ledger_id")
                for item in events[i:j]
                if item.detail.get("ledger_id") is not None
            ]
            hp_str = f"HP→{hp}" if hp is not None else ""
            src = f" [{skill}]" if skill else ""
            result.append(FormattedEvent(
                kind="damage",
                round=event.round,
                summary=f"{target} 受到 {damage}x{count} 伤害 ({hp_str}){src}",
                detail={
                    **event.detail,
                    "hit_count": count,
                    "hp_after": last.detail.get("hp_after"),
                    "ledger_ids": ledger_ids,
                },
                icon=event.icon,
                color=event.color,
            ))
        else:
            result.append(event)
        i = j
    return result


def _target_display(detail: dict) -> str:
    target_side = detail.get("target_side", "")
    target_name = detail.get("target_name")
    if target_name and target_name != target_side:
        return f"{target_side}({target_name})"
    return target_side
