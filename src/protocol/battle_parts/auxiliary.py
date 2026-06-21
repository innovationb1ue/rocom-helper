"""Auxiliary battle opcode extraction compatibility facade."""
from __future__ import annotations

from src.protocol.battle_parts.auxiliary_actions import (
    extract_01a9_action,
    extract_0220_handle,
)
from src.protocol.battle_parts.auxiliary_creatures import (
    extract_0102_creatures,
    extract_0102_metadata,
)
from src.protocol.battle_parts.auxiliary_simple import (
    extract_1305_load_finish_req,
    extract_1306_load_finish_rsp,
    extract_1309_supply_pet_req,
    extract_130a_supply_pet_rsp,
    extract_1326_auto_cmd,
    extract_132a_role_leave,
    extract_132d_force_finish,
    extract_132e_player_runaway_req,
    extract_132f_player_runaway_rsp,
    extract_1334_emoji,
    extract_1335_round_op_query_req,
    extract_1336_round_op_query_rsp,
    extract_133c_catch_rsp,
    extract_13f6_ai_skill,
    extract_13f9_pk_again,
)

__all__ = [
    "extract_0102_creatures",
    "extract_0102_metadata",
    "extract_01a9_action",
    "extract_0220_handle",
    "extract_1305_load_finish_req",
    "extract_1306_load_finish_rsp",
    "extract_1309_supply_pet_req",
    "extract_130a_supply_pet_rsp",
    "extract_1326_auto_cmd",
    "extract_132a_role_leave",
    "extract_132d_force_finish",
    "extract_132e_player_runaway_req",
    "extract_132f_player_runaway_rsp",
    "extract_1334_emoji",
    "extract_1335_round_op_query_req",
    "extract_1336_round_op_query_rsp",
    "extract_133c_catch_rsp",
    "extract_13f6_ai_skill",
    "extract_13f9_pk_again",
]
