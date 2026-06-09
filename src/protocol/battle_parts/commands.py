"""Command opcode extraction compatibility facade."""
from __future__ import annotations

from src.protocol.battle_parts.command_refresh import extract_13f4_refresh
from src.protocol.battle_parts.command_results import extract_130c_result
from src.protocol.battle_parts.command_skills import (
    extract_130b_skill_select,
    extract_1322_skill_declare,
)

__all__ = [
    "extract_130b_skill_select",
    "extract_130c_result",
    "extract_1322_skill_declare",
    "extract_13f4_refresh",
]
