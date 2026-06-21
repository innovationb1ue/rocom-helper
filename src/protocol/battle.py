"""Battle protocol extraction compatibility facade.

The public ``extract_*`` functions remain importable from this module while
implementations live under ``src.protocol.battle_parts`` by opcode family.
"""
from __future__ import annotations

from src.protocol.battle_parts.action_resolve import (
    _extract_1324_entry,
    _extract_perform_cmd,
    extract_1324_action,
    extract_13f3_preplay,
    extract_13fc_pvp_perform,
)
from src.protocol.battle_parts.auxiliary import (
    extract_0102_creatures,
    extract_0102_metadata,
    extract_01a9_action,
    extract_0220_handle,
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
from src.protocol.battle_parts.commands import (
    extract_130b_skill_select,
    extract_130c_result,
    extract_1322_skill_declare,
    extract_13f4_refresh,
)
from src.protocol.battle_parts.lifecycle import (
    BATTLE_RESULT_MAP,
    extract_1312_round_flow,
    extract_1313_round_confirm,
    extract_1314_round_confirm_rsp,
    extract_1316_enter,
    extract_131a_round_start,
    extract_132c_finish,
)

__all__ = [
    "BATTLE_RESULT_MAP",
    "_extract_1324_entry",
    "_extract_perform_cmd",
    "extract_0102_creatures",
    "extract_0102_metadata",
    "extract_01a9_action",
    "extract_0220_handle",
    "extract_1305_load_finish_req",
    "extract_1306_load_finish_rsp",
    "extract_1309_supply_pet_req",
    "extract_130a_supply_pet_rsp",
    "extract_130b_skill_select",
    "extract_130c_result",
    "extract_1312_round_flow",
    "extract_1313_round_confirm",
    "extract_1314_round_confirm_rsp",
    "extract_1316_enter",
    "extract_131a_round_start",
    "extract_1322_skill_declare",
    "extract_1324_action",
    "extract_1326_auto_cmd",
    "extract_132a_role_leave",
    "extract_132c_finish",
    "extract_132d_force_finish",
    "extract_132e_player_runaway_req",
    "extract_132f_player_runaway_rsp",
    "extract_1334_emoji",
    "extract_1335_round_op_query_req",
    "extract_1336_round_op_query_rsp",
    "extract_133c_catch_rsp",
    "extract_13f3_preplay",
    "extract_13f4_refresh",
    "extract_13f6_ai_skill",
    "extract_13f9_pk_again",
    "extract_13fc_pvp_perform",
]
