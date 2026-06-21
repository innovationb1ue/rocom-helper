"""Action-resolve dispatch loop for BattleStateTracker."""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.state.action_entries import ENTRY_HANDLERS
from src.analysis.state.field_events import GLOBAL_EVENT_KINDS


def handle_action_resolve(tracker: Any, detail: Dict[str, Any]) -> None:
    """Dispatch action-resolve entries to focused entry handlers."""
    for entry in detail.get("entries", []):
        tracker._record_perform_group(entry)
        if entry.get("kind") in GLOBAL_EVENT_KINDS:
            tracker._record_global_event(entry["kind"], entry)
        handler_name = ENTRY_HANDLERS.get(entry.get("kind"))
        if handler_name:
            getattr(tracker, handler_name)(entry)
        tracker._apply_entry_sync_data(entry)
