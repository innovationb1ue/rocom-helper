"""Lifecycle constants and helpers for battle protocol extraction."""
from __future__ import annotations

from typing import Dict

BATTLE_RESULT_MAP: Dict[int, str] = {
    0: "NULL",
    2: "WIN",
    4: "LOSE",
    10: "MONSTER_RUNAWAY",
    12: "RUNAWAY",
    260: "RUNAWAY_ROLE_MAGIC",
    18: "WIN_DEFEAT",
    34: "WIN_CATCH",
    66: "WIN_HP",
    68: "LOSE_HP",
    132: "MONSTER_ESCAPE",
    516: "MONSTER_ESCAPE2",
}
