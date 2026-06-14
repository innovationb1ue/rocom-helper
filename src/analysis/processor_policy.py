"""Processing policy helpers for BattleProcessor orchestration."""
from __future__ import annotations

from typing import Any, Dict, Iterable

from src.analysis.constants import OPCODE_ACTION_RESOLVE, OPCODE_ROUND_START


def should_snapshot_state_before(*, include_analysis: bool, opcode: int) -> bool:
    return include_analysis and opcode == OPCODE_ACTION_RESOLVE


def battle_is_active(state: Dict[str, Any]) -> bool:
    return (
        state.get("battle_id") is not None
        and state.get("result") is None
        and state.get("phase") != "settling"
        and not state.get("terminal_pending")
    )


def should_compute_damage_analysis(
    *,
    include_analysis: bool,
    active: bool,
    opcode: int,
    damage_opcodes: Iterable[int],
) -> bool:
    return include_analysis and active and opcode in damage_opcodes


def should_compute_tactical(*, include_analysis: bool, active: bool, opcode: int) -> bool:
    return include_analysis and active and opcode in (OPCODE_ACTION_RESOLVE, OPCODE_ROUND_START)
