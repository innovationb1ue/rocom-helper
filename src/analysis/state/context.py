"""Shared mutable context for BattleStateTracker internals."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, MutableMapping, MutableSet, Optional

from src.analysis.state_helpers import append_bounded


@dataclass
class BattleStateContext:
    """Small holder for state-machine side tables and current event metadata."""

    state: Dict[str, Any]
    battle_side_pets: MutableMapping[int, Dict[str, Any]]
    player_slots: MutableSet[int]
    opponent_slots: MutableSet[int]
    current_opcode: Optional[int] = None
    current_event_detail: Dict[str, Any] = field(default_factory=dict)

    def field_context(self) -> Dict[str, Any]:
        ctx = self.state.setdefault("field_context", {
            "weather_current": self.state.get("weather"),
            "weather_history": [],
            "global_events": [],
        })
        ctx.setdefault("perform_groups", [])
        ctx.setdefault("sync_events", [])
        ctx.setdefault("item_sync_events", [])
        ctx.setdefault("damage_ledger", [])
        ctx.setdefault("reflect_candidates", [])
        return ctx

    @staticmethod
    def append_bounded(items: List[Dict[str, Any]], item: Dict[str, Any], limit: int) -> None:
        append_bounded(items, item, limit)
