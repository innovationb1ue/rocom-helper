"""Battle state helper package.

`src.analysis.battle_state.BattleStateTracker` remains the compatibility
facade. Modules in this package own focused state-machine responsibilities:

- `lifecycle`: initial state construction.
- `lifecycle_events`: lifecycle opcode state transitions.
- `wrapper_sync`: round/action wrapper synchronization into pet runtime state.
- `weather`: weather lookup and current-weather writes.
- `context`: mutable side tables and field-context helpers.
- `event_dispatch`: raw event history, current-event context, and opcode dispatch.
- `snapshot`: external state snapshot projection and derived speed fields.
- `hp_ledger`: HP mutation, damage ledger, and per-pet HP traces.
- `field_events`: global event, perform group, sync, and item-sync histories.
- `skill_runtime`: skill runtime sync and battle skill pool normalization.
- `pet_runtime`: pet sync, pet info sync, wrapper runtime fields, and data-update skills.
- `side_resolver`: side-slot ownership, active-pet lookup, and stable identity matching.
- `entries_*`: action-entry handlers grouped by event family.
- `pet_sync`: side/slot ownership helpers.
"""

from src.analysis.state.lifecycle import build_initial_state
from src.analysis.state.pet_sync import bind_side_slot, side_int, side_is_player

__all__ = ["bind_side_slot", "build_initial_state", "side_int", "side_is_player"]
