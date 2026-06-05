"""Lifecycle helpers for battle state initialization/reset."""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.state_helpers import initial_battle_state


def build_initial_state() -> Dict[str, Any]:
    """Return a fresh battle state dict used by BattleStateTracker."""
    return initial_battle_state()
