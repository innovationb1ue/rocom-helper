"""Core battle lifecycle opcode extraction."""
from __future__ import annotations

from typing import Any, Dict

from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    first_sub,
    first_text,
    pick_first,
    extract_state_wrappers_from_record,
)
from src.protocol.battle_schema import (
    _as_list,
    _enum_name,
    _enum_value,
    _first_value,
    _schema_payload,
    _schema_quality,
)


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


def extract_1316_enter(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract battle-enter details from opcode 0x1316."""
    decoded = _schema_payload(record, "ZoneBattleEnterNotify")
    if decoded is not None:
        init_info = decoded.get("init_info") if isinstance(decoded.get("init_info"), dict) else {}
        npc_ids = [_enum_value(v) for v in _as_list(decoded.get("npc_id"))]
        battle_cfg_ids = [_enum_value(v) for v in _as_list(init_info.get("battle_cfg_id"))]
        battle_state = init_info.get("battle_state")

        detail: Dict[str, Any] = {
            "battle_mode": _enum_value(decoded.get("battle_mode")),
            "round": _enum_value(decoded.get("round")),
            "series_index": _enum_value(decoded.get("series_index")),
            "round_time": _enum_value(decoded.get("round_time")),
            "npc_id": _first_value(npc_ids),
            "npc_ids": [v for v in npc_ids if v is not None],
            "is_reconnect": bool(decoded.get("is_reconnect") or False),
            "enter_battle_type": _enum_value(decoded.get("enter_battle_type")),
            "weather_id": _enum_value(decoded.get("weather_id")),
            "weather_expire_round": _enum_value(decoded.get("weather_expire_round")),
            "max_round": _enum_value(decoded.get("max_round")),
            "creater_uin": _enum_value(decoded.get("creater_uin")),
            "data_seq_num": _enum_value(decoded.get("data_seq_num")),
            "battle_id": _enum_value(init_info.get("battle_id")),
            "battle_cfg_id": _first_value(battle_cfg_ids),
            "battle_cfg_ids": [v for v in battle_cfg_ids if v is not None],
            "battle_start_time": _enum_value(init_info.get("battle_start_time")),
            "battle_state": _enum_value(battle_state),
            "battle_state_name": _enum_name(battle_state),
        }
        if isinstance(decoded.get("battle_center"), dict):
            detail["battle_center"] = decoded["battle_center"]
        detail["wrappers"] = extract_state_wrappers_from_record(record)
        _schema_quality(detail, message="ZoneBattleEnterNotify", found=True)
        detail["opcode"] = record.get("opcode")
        detail["opcode_hex"] = record.get("opcode_hex", "")
        return detail

    root = record["root"]
    rg = field_groups(root)
    detail: Dict[str, Any] = {
        "battle_mode": pick_first(collect_varints(root, 1)),
        "round": pick_first(collect_varints(root, 2)),
        "series_index": pick_first(collect_varints(root, 3)),
        "round_time": pick_first(collect_varints(root, 4)),
        "npc_id": pick_first(collect_varints(root, 9)),
        "is_reconnect": bool(pick_first(collect_varints(root, 10)) or 0),
        "enter_battle_type": pick_first(collect_varints(root, 11)),
        "weather_id": pick_first(collect_varints(root, 13)),
        "max_round": pick_first(collect_varints(root, 15)),
        "creater_uin": pick_first(collect_varints(root, 17)),
        "data_seq_num": pick_first(collect_varints(root, 18)),
    }
    init_sub = first_sub(rg.get(6, []))
    if init_sub:
        detail["battle_id"] = pick_first(collect_varints(init_sub, 1))
        detail["battle_cfg_id"] = pick_first(collect_varints(init_sub, 2))
    detail["wrappers"] = extract_state_wrappers_from_record(record)
    _schema_quality(detail, message="ZoneBattleEnterNotify", found=False)
    detail["opcode"] = record.get("opcode")
    detail["opcode_hex"] = record.get("opcode_hex", "")
    return detail


def extract_131a_round_start(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract round-start details from opcode 0x131A."""
    decoded = _schema_payload(record, "ZoneBattleRoundStartNotify")
    if decoded is not None:
        state_type = decoded.get("state_type")
        state_info = decoded.get("state_info") if isinstance(decoded.get("state_info"), dict) else {}
        perform_cmd = decoded.get("perform_cmd") if isinstance(decoded.get("perform_cmd"), dict) else None
        npc_escape = [_enum_value(v) for v in _as_list(state_info.get("npc_escape"))]

        detail: Dict[str, Any] = {
            "state_type": _enum_value(state_type),
            "state_type_name": _enum_name(state_type),
            "has_npc_delay": bool(decoded.get("has_npc_delay") or False),
            "guide_id": _enum_value(decoded.get("guide_id")),
            "battle_id": _enum_value(state_info.get("battle_id")),
            "round": _enum_value(state_info.get("round")),
            "series_index": _enum_value(state_info.get("series_index")),
            "round_time": _enum_value(state_info.get("round_time")),
            "npc_escape": _first_value(npc_escape),
            "npc_escape_list": [v for v in npc_escape if v is not None],
            "has_perform": perform_cmd is not None,
        }
        if perform_cmd is not None:
            detail["is_battle_finished"] = bool(perform_cmd.get("is_battle_finished") or False)
            detail["perform_round"] = _enum_value(perform_cmd.get("round"))
            detail["perform_seq_num"] = _enum_value(perform_cmd.get("seq_num"))
        detail["wrappers"] = extract_state_wrappers_from_record(record)
        _schema_quality(detail, message="ZoneBattleRoundStartNotify", found=True)
        detail["opcode"] = record.get("opcode")
        detail["opcode_hex"] = record.get("opcode_hex", "")
        return detail

    root = record["root"]
    rg = field_groups(root)
    detail: Dict[str, Any] = {
        "state_type": pick_first(collect_varints(root, 1)),
        "has_npc_delay": bool(pick_first(collect_varints(root, 5)) or 0),
        "guide_id": pick_first(collect_varints(root, 6)),
    }
    state_sub = first_sub(rg.get(2, []))
    if state_sub:
        detail["battle_id"] = pick_first(collect_varints(state_sub, 1))
        detail["round"] = pick_first(collect_varints(state_sub, 2))
        detail["series_index"] = pick_first(collect_varints(state_sub, 3))
        detail["round_time"] = pick_first(collect_varints(state_sub, 5))
        detail["npc_escape"] = pick_first(collect_varints(state_sub, 11))
    pcmd = first_sub(rg.get(3, []))
    if pcmd:
        detail["has_perform"] = True
        detail["is_battle_finished"] = bool(pick_first(collect_varints(pcmd, 1)) or 0)
    detail["wrappers"] = extract_state_wrappers_from_record(record)
    _schema_quality(detail, message="ZoneBattleRoundStartNotify", found=False)
    detail["opcode"] = record.get("opcode")
    detail["opcode_hex"] = record.get("opcode_hex", "")
    return detail


def extract_132c_finish(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract battle-finish details from opcode 0x132C."""
    decoded = _schema_payload(record, "ZoneBattleFinishNotify")
    if decoded is not None:
        settle = decoded.get("settle_info") if isinstance(decoded.get("settle_info"), dict) else {}
        result = settle.get("result")
        result_code = _enum_value(result)
        ret = decoded.get("ret_info") if isinstance(decoded.get("ret_info"), dict) else {}

        pet_infos = []
        for item in _as_list(decoded.get("pet_info")):
            if not isinstance(item, dict):
                continue
            pet_infos.append({
                "pet_gid": _enum_value(item.get("pet_gid")),
                "remain_hp": _enum_value(item.get("remain_hp")),
                "remain_energy": _enum_value(item.get("remain_energy")),
                "mod_energy": _enum_value(item.get("mod_energy")),
                "battle_max_hp": _enum_value(item.get("battle_max_hp")),
                "uin": _enum_value(item.get("uin")),
            })

        detail: Dict[str, Any] = {
            "evolution_complete": bool(decoded.get("evolution_complete") or False),
            "will_leave_visit": bool(decoded.get("will_leave_visit") or False),
            "pvp_score": _enum_value(decoded.get("pvp_score")),
            "total_pvp_score": _enum_value(decoded.get("total_pvp_score")),
            "max_pvp_score": _enum_value(decoded.get("max_pvp_score")),
            "create_battle_ret": _enum_value(decoded.get("create_battle_ret")),
            "result_code": result_code,
            "result_name": BATTLE_RESULT_MAP.get(result_code, f"UNKNOWN({result_code})") if result_code is not None else None,
            "result_enum_name": _enum_name(result),
            "battle_conf_type": _enum_value(settle.get("battle_conf_type")),
            "battle_opposite_type": _enum_value(settle.get("battle_opposite_type")),
            "battle_conf_id": _enum_value(settle.get("battle_conf_id")),
            "is_surrender": bool(settle.get("is_surrender") or False),
            "battle_id": _enum_value(settle.get("battle_id")),
            "rounds": _enum_value(settle.get("rounds")),
            "seconds": _enum_value(settle.get("seconds")),
            "escape_style": _enum_value(settle.get("escape_style")),
            "seen_monster_ids": [
                v for v in (_enum_value(item) for item in _as_list(decoded.get("seen_monster_id")))
                if v is not None
            ],
        }
        if ret:
            detail["ret_code"] = _enum_value(ret.get("ret_code"))
            detail["ret_msg"] = ret.get("ret_msg")
        if pet_infos:
            detail["finish_pet_infos"] = pet_infos
        _schema_quality(detail, message="ZoneBattleFinishNotify", found=True)
        detail["opcode"] = record.get("opcode")
        detail["opcode_hex"] = record.get("opcode_hex", "")
        return detail

    root = record["root"]
    rg = field_groups(root)
    detail: Dict[str, Any] = {
        "evolution_complete": bool(pick_first(collect_varints(root, 7)) or 0),
        "will_leave_visit": bool(pick_first(collect_varints(root, 10)) or 0),
        "pvp_score": pick_first(collect_varints(root, 14)),
    }
    settle = first_sub(rg.get(1, []))
    if settle:
        result_code = pick_first(collect_varints(settle, 6))
        detail["result_code"] = result_code
        detail["result_name"] = BATTLE_RESULT_MAP.get(result_code, f"UNKNOWN({result_code})") if result_code is not None else None
        detail["battle_conf_type"] = pick_first(collect_varints(settle, 1))
        detail["battle_opposite_type"] = pick_first(collect_varints(settle, 2))
        detail["battle_conf_id"] = pick_first(collect_varints(settle, 7))
        detail["is_surrender"] = bool(pick_first(collect_varints(settle, 14)) or 0)
        detail["battle_id"] = pick_first(collect_varints(settle, 19))
        detail["rounds"] = pick_first(collect_varints(settle, 37))
        detail["seconds"] = pick_first(collect_varints(settle, 38))
        detail["escape_style"] = pick_first(collect_varints(settle, 10))
    detail["seen_monster_ids"] = collect_varints(root, 3)
    ret = first_sub(rg.get(4, []))
    if ret:
        detail["ret_code"] = pick_first(collect_varints(ret, 1))
        detail["ret_msg"] = first_text(ret, 2)
    pet_infos = []
    for entry in rg.get(8, []):
        sub = entry.get("sub")
        if not sub:
            continue
        pet_infos.append({
            "pet_gid": pick_first(collect_varints(sub, 1)),
            "remain_hp": pick_first(collect_varints(sub, 2)),
            "remain_energy": pick_first(collect_varints(sub, 3)),
            "battle_max_hp": pick_first(collect_varints(sub, 5)),
        })
    if pet_infos:
        detail["finish_pet_infos"] = pet_infos
    _schema_quality(detail, message="ZoneBattleFinishNotify", found=False)
    detail["opcode"] = record.get("opcode")
    detail["opcode_hex"] = record.get("opcode_hex", "")
    return detail
