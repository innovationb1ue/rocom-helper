"""Simple schema/raw auxiliary battle opcode extraction."""
from __future__ import annotations

from src.protocol.battle_schema import _make_simple_extractor


extract_1326_auto_cmd = _make_simple_extractor("ChangeAutoCmdNotify")
extract_1326_auto_cmd.__doc__ = """0x1326 ChangeAutoCmdNotify - auto battle toggle."""

extract_1305_load_finish_req = _make_simple_extractor("ZoneBattleLoadFinishReq")
extract_1306_load_finish_rsp = _make_simple_extractor("ZoneBattleLoadFinishRsp")
extract_1309_supply_pet_req = _make_simple_extractor("ZoneBattleSupplyPetReq")
extract_130a_supply_pet_rsp = _make_simple_extractor("ZoneBattleSupplyPetRsp")

extract_132a_role_leave = _make_simple_extractor("RoleLeaveNotify")
extract_132a_role_leave.__doc__ = """0x132A RoleLeaveNotify - player disconnect."""

extract_132e_player_runaway_req = _make_simple_extractor("ZoneBattlePlayerRunawayReq")
extract_132f_player_runaway_rsp = _make_simple_extractor("ZoneBattlePlayerRunawayRsp")

extract_132d_force_finish = _make_simple_extractor("BattleForceFinishNotify")
extract_132d_force_finish.__doc__ = """0x132D BattleForceFinishNotify - forced battle end."""

extract_1334_emoji = _make_simple_extractor("EmojiNotify")
extract_1334_emoji.__doc__ = """0x1334 EmojiNotify - battle emote."""

extract_133c_catch_rsp = _make_simple_extractor("CatchConfirmRsp")
extract_133c_catch_rsp.__doc__ = """0x133C CatchConfirmRsp - capture result."""

extract_13f6_ai_skill = _make_simple_extractor("AiSelectSkillNotify")
extract_13f6_ai_skill.__doc__ = """0x13F6 AiSelectSkillNotify - AI skill hint."""

extract_1335_round_op_query_req = _make_simple_extractor("ZoneBattleRoundOpQueryReq")
extract_1336_round_op_query_rsp = _make_simple_extractor("ZoneBattleRoundOpQueryRsp")
extract_13f9_pk_again = _make_simple_extractor("ZoneBattlePkAgainNotify")

__all__ = [
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
