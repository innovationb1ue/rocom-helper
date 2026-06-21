"""Lifecycle opcode extraction compatibility facade."""
from __future__ import annotations

from src.protocol.battle_parts.lifecycle_core import (
    BATTLE_RESULT_MAP,
    extract_1316_enter,
    extract_131a_round_start,
    extract_132c_finish,
)
from src.protocol.battle_parts.lifecycle_flow import (
    extract_1312_round_flow,
    extract_1313_round_confirm,
    extract_1314_round_confirm_rsp,
)

__all__ = [
    "BATTLE_RESULT_MAP",
    "extract_1312_round_flow",
    "extract_1313_round_confirm",
    "extract_1314_round_confirm_rsp",
    "extract_1316_enter",
    "extract_131a_round_start",
    "extract_132c_finish",
]
