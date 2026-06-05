"""State-tracker helper package.

`BattleStateTracker` remains the compatibility facade in
`src.analysis.battle_state`; helpers live here as the first step toward
splitting lifecycle, pet sync, and action-entry handling.
"""

from src.analysis.state.lifecycle import build_initial_state
from src.analysis.state.pet_sync import bind_side_slot, side_int, side_is_player

__all__ = ["bind_side_slot", "build_initial_state", "side_int", "side_is_player"]
