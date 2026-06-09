"""Damage ledger matching helpers for replay audit samples."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def ledger_records_for_damage(state: Dict[str, Any], detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    ledger = ((state.get("field_context") or {}).get("damage_ledger") or [])
    by_id = {
        str(item.get("ledger_id")): item
        for item in ledger
        if item.get("ledger_id")
    }
    wanted = [str(item) for item in detail.get("ledger_ids") or []]
    if detail.get("ledger_id") is not None:
        wanted.append(str(detail["ledger_id"]))
    wanted = list(dict.fromkeys(wanted))
    records = [by_id[item] for item in wanted if item in by_id]
    if records:
        return records
    skill_name = detail.get("skill_name")
    hp_after = detail.get("hp_after")
    candidates = [
        item for item in ledger
        if item.get("event_kind") == "damage"
        and item.get("skill_name") == skill_name
        and (hp_after is None or item.get("hp_after") == hp_after)
    ]
    return candidates[-1:] if candidates else []


def ledger_actual_damage(item: Dict[str, Any]) -> int:
    if item.get("actual_damage") is not None:
        return max(0, int(item["actual_damage"]))
    if item.get("damage") is not None:
        return max(0, int(item["damage"]))
    before = item.get("hp_before")
    after = item.get("hp_after")
    if before is not None and after is not None:
        return max(0, int(before) - int(after))
    return 0


def find_prediction(
    advice: Optional[Dict[str, Any]], skill_name: str, target_side: str,
) -> Optional[Dict[str, Any]]:
    if not advice:
        return None
    key = "skill_analysis" if target_side == "敌方" else "opp_skill_analysis"
    for pred in advice.get(key, []):
        if pred.get("skill_name") == skill_name:
            return pred
    return None
