"""战斗协议提取模块。

从解析后的 protobuf 记录中提取战斗语义信息。每个 extract_* 函数对应一个 opcode。

提取策略 — 双轨制:
  1. Schema-first: 通过 proto_schema.json 定义的 Protobuf 消息结构解码
  2. Raw fallback: 手动遍历 protobuf 字段树提取数据

两者产生相同的输出结构，_schema_quality() 标记解析质量。

主要 opcode 对应:
  0x0102 = 精灵名册初始化
  0x130B = 客户端技能选择
  0x1322 = 服务端技能声明
  0x1324 = 行动结算（核心，包含伤害/效果/换宠/击杀等子事件）
  0x130C = 行动确认
  0x13F4 = 特殊刷新（技能选项/能量）
  0x1316 = 进入战斗
  0x131A = 回合开始
  0x132C = 战斗结束
  0x13FC = PVP 演出
  0x13F3 = 预演出
  0x1312 = 回合流
"""
from __future__ import annotations

import logging
import struct
from typing import Any, Dict, List, Optional

from src.protocol.proto_core import (
    SDT_TO_TYPE,
    collect_varints,
    field_groups,
    first_sub,
    first_text,
    maybe_signed64,
    normalize_skill_id,
    parse_proto_message,
    pick_first,
    read_varint,
    side_name,
    skill_name,
    buff_name,
    _attach_skill_meta,
    _attach_buff_meta,
    _attach_buffbase_meta,
    _extract_actor_target,
    extract_state_wrappers_from_record,
    extract_creature,
    _WILLPOWER_SKILL_ID,
    _ENERGY_BOTTLE_MAX,
    SPECIAL_ACTION_COMMANDS,
    SPECIAL_ACTION_SHAPES,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema-first 辅助函数
# 用于从 proto_schema.json 解码的结构化数据中提取值。
# _schema_payload: 获取已解码的 schema 数据（如果存在）
# _enum_value/_enum_name: 处理枚举类型值（schema 中的 {value, name} 结构）
# _schema_quality: 标记解析质量（schema_postprocess vs raw_field_postprocess）
# ---------------------------------------------------------------------------

def _schema_payload(record: Dict[str, Any], expected_message: str) -> Optional[Dict[str, Any]]:
    decoded = record.get("_decoded")
    if isinstance(decoded, dict) and decoded:
        message_name = record.get("_message_name")
        if message_name in (None, "", expected_message):
            return decoded
    return None


def _enum_value(value: Any) -> Optional[int]:
    if isinstance(value, dict):
        return _enum_value(value.get("value"))
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return None


def _enum_name(value: Any) -> Optional[str]:
    return value.get("name") if isinstance(value, dict) and isinstance(value.get("name"), str) else None


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _first_value(value: Any) -> Any:
    items = _as_list(value)
    return items[0] if items else None


def _weather_name(weather_id: Optional[int]) -> Optional[str]:
    if weather_id is None:
        return None
    from src.data.loader import get_weather
    meta = get_weather(weather_id)
    if isinstance(meta, dict) and meta.get("name"):
        return meta["name"]
    return None


def _schema_quality(
    detail: Dict[str, Any],
    *,
    message: str,
    found: bool,
    level: str = "battle_semantic",
) -> Dict[str, Any]:
    detail.update({
        "schema_message": message,
        "schema_found": found,
        "parse_quality": "schema_postprocess" if found else "raw_field_postprocess",
        "semantic_level": level,
    })
    return detail


# ---------------------------------------------------------------------------
# Core skill / action extraction
# ---------------------------------------------------------------------------

def _extract_skill_ref(msg: Dict[str, Any], *, skill_field: int = 3) -> Dict[str, Any]:
    """Extract a skill reference from a sub-message (fields 1=actor, 2=target, 3=skill)."""
    all_field_values = collect_varints(msg, skill_field)
    skill_id_x100 = pick_first(all_field_values, low=100_000)
    sid = normalize_skill_id(skill_id_x100)

    skill_slot_index: Optional[int] = None
    if skill_id_x100 is None:
        raw_small = [v for v in all_field_values if 1 <= v <= 10]
        if raw_small:
            skill_slot_index = raw_small[0]

    actor = pick_first(collect_varints(msg, 1))
    target = pick_first(collect_varints(msg, 2))
    out: Dict[str, Any] = {
        "actor_side": actor,
        "actor_side_name": side_name(actor),
        "target_side": target,
        "target_side_name": side_name(target),
        "skill_id_x100": skill_id_x100,
        "skill_id": sid,
        "skill_name": skill_name(sid),
        "skill_slot_index": skill_slot_index,
    }
    _attach_skill_meta(out, sid)
    return out


def _extract_special_action(
    msg: Dict[str, Any],
    *,
    command_flag: Optional[int] = None,
    command_slot: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Try to interpret *msg* as a special-action (willpower, energy-bottle, switch)."""
    kind = pick_first(collect_varints(msg, 1), low=0, high=99)
    if kind is None:
        return None

    # Try field 8 -> 4 -> 3 for a nested payload
    sub: Optional[Dict[str, Any]] = None
    payload_branch: Optional[int] = None
    for branch in (8, 4, 3):
        entries = field_groups(msg).get(branch, [])
        s = first_sub(entries)
        if s is not None:
            sub = s
            payload_branch = branch
            break

    if sub is None:
        return None

    # Determine action_name
    action_name: Optional[str] = None
    lookup_key: Optional[tuple] = None
    if command_flag is not None and command_slot is not None:
        lookup_key = (command_flag, command_slot)
        action_name = SPECIAL_ACTION_COMMANDS.get(lookup_key)  # type: ignore[arg-type]
    if action_name is None and kind is not None and payload_branch is not None:
        lookup_key = (kind, payload_branch)
        action_name = SPECIAL_ACTION_SHAPES.get(lookup_key)  # type: ignore[arg-type]

    if action_name is None:
        return None

    out: Dict[str, Any] = {
        "action_kind": "special_action",
        "action_name": action_name,
        "payload_kind": kind,
        "payload_branch": payload_branch,
        "command_flag": command_flag,
        "command_slot": command_slot,
    }
    # If sub has actor/target fields, include them
    actor = pick_first(collect_varints(sub, 1))
    target = pick_first(collect_varints(sub, 2))
    out["actor_side"] = actor
    out["actor_side_name"] = side_name(actor)
    out["target_side"] = target
    out["target_side_name"] = side_name(target)
    return out


def _extract_skill_or_special(
    record: Dict[str, Any],
    *,
    extra_fields: Dict[str, Any],
    command_flag: Optional[int] = None,
    command_slot: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Try to extract a skill or special action from *record*'s root."""
    root = record.get("root")
    if root is None:
        return None

    groups = field_groups(root)
    # The payload sub-message is in field 2
    f2 = groups.get(2, [])
    payload = first_sub(f2)
    if payload is None:
        return None

    out: Optional[Dict[str, Any]] = None

    # 1. Try skill extraction
    skill_id_x100 = pick_first(collect_varints(payload, 3), low=100_000)
    if skill_id_x100 is not None:
        out = _extract_skill_ref(payload)
    else:
        # Check nested sub in field 3 for skill info
        f3 = field_groups(payload).get(3, [])
        f3_sub = first_sub(f3)
        if f3_sub is not None:
            sid3 = pick_first(collect_varints(f3_sub, 3), low=100_000)
            if sid3 is not None:
                out = _extract_skill_ref(f3_sub)

    # 1b. Fallback: check for slot index (small values 1-10)
    if out is None:
        raw_all = collect_varints(payload, 3)
        raw_small = [v for v in raw_all if 1 <= v <= 10]
        if raw_small:
            actor = pick_first(collect_varints(payload, 1))
            target = pick_first(collect_varints(payload, 2))
            out = {
                "actor_side": actor,
                "actor_side_name": side_name(actor),
                "target_side": target,
                "target_side_name": side_name(target),
                "skill_id": None,
                "skill_name": None,
                "skill_slot_index": raw_small[0],
            }

    # 2. Try special action
    if out is None:
        out = _extract_special_action(payload, command_flag=command_flag, command_slot=command_slot)

    if out is None:
        return None

    out.update(extra_fields)
    out["opcode"] = record.get("opcode")
    out["opcode_hex"] = record.get("opcode_hex", "")
    return out


# ---------------------------------------------------------------------------
# 0x130b - Skill select
# ---------------------------------------------------------------------------

def extract_130b_skill_select(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract skill-selection details from opcode 0x130B."""
    root = record.get("root")
    if root is None:
        return None

    cmd_slot = pick_first(collect_varints(root, 5))
    cmd_flag = pick_first(collect_varints(root, 1))

    extra: Dict[str, Any] = {
        "cmd_slot": cmd_slot,
        "cmd_flag": cmd_flag,
    }

    result = _extract_skill_or_special(
        record,
        extra_fields=extra,
        command_flag=cmd_flag,
        command_slot=cmd_slot,
    )
    if result is not None:
        result["extract_kind"] = "skill_select"
    return result


# ---------------------------------------------------------------------------
# 0x1322 - Skill declare
# ---------------------------------------------------------------------------

def extract_1322_skill_declare(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract skill-declaration details from opcode 0x1322."""
    root = record.get("root")
    if root is None:
        return None

    battle_token = pick_first(collect_varints(root, 1))

    extra: Dict[str, Any] = {
        "battle_token": battle_token,
    }

    result = _extract_skill_or_special(record, extra_fields=extra)
    if result is not None:
        result["extract_kind"] = "skill_declare"
    return result


# ---------------------------------------------------------------------------
# 0x130c - Result
# ---------------------------------------------------------------------------

def extract_130c_result(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract battle-result details from opcode 0x130C."""
    root = record.get("root")
    if root is None:
        return None

    rg = field_groups(root)
    container = first_sub(rg.get(10, []))
    state_msg = first_sub(field_groups(container).get(2, [])) if container else None

    skill_ctn = first_sub(rg.get(11, []))
    skill_msg = first_sub(field_groups(skill_ctn).get(2, [])) if skill_ctn else None

    out: Dict[str, Any] = _extract_skill_ref(skill_msg, skill_field=1) if skill_msg else {}

    btok_msg = first_sub(field_groups(container).get(1, [])) if container else None
    out.update({
        "battle_token": pick_first(collect_varints(btok_msg, 1)),
        "current_hp": pick_first(collect_varints(state_msg, 3), low=0, high=99999) if state_msg else None,
        "energy_after": pick_first(collect_varints(state_msg, 26), low=0, high=99) if state_msg else None,
        "result_code": pick_first(collect_varints(first_sub(rg.get(1, [])), 1), low=0, high=999),
        "opcode": record.get("opcode"),
        "opcode_hex": record.get("opcode_hex", ""),
    })

    if skill_ctn and out.get("skill_id") is None:
        sp = _extract_special_action(skill_ctn)
        if sp:
            out.update(sp)

    wrappers = extract_state_wrappers_from_record(record)
    if wrappers:
        out["state_wrappers"] = wrappers

    if out.get("skill_id") is None:
        inferred = _infer_action_from_wrappers(wrappers or [])
        if inferred:
            out["action_kind"] = "special_action"
            out["action_name"] = inferred

    semantic_keys = (
        "battle_token", "current_hp", "energy_after", "result_code",
        "skill_id", "skill_name", "skill_id_x100", "action_name",
        "action_kind", "state_wrappers",
    )
    return out if any(out.get(key) is not None for key in semantic_keys) else None


def _infer_action_from_wrappers(wrappers: List[Dict[str, Any]]) -> Optional[str]:
    """Infer willpower action by checking if any wrapper has the willpower skill."""
    return "愿力强化" if any(
        any(int(sk.get("skill_id") or 0) == _WILLPOWER_SKILL_ID
            for sk in (w.get("dynamic_skills") or []))
        for w in wrappers
    ) else None


# ---------------------------------------------------------------------------
# 0x1324 - Action / perform entries
# ---------------------------------------------------------------------------
# _extract_1324_entry 解析 action resolve 中的单个条目。
# entry_type (field 1) 决定条目类型:
#   1=skill_cast, 4=damage, 2=effect_apply, 3=effect_stage,
#   5=heal, 6=energy, 7=defeat, 8=revive, 9=effect_trigger,
#   10=effect_link, 11=sp_energy_change, 12=sp_energy_trigger,
#   13=change_pet, 15=idle, 19=skill_state, 22=weather_change,
#   23=notify_perform, 25=ai_action, 29=role_skill_cast,
#   30=combo_skill_cast, 34=pvp_perform_marker, 35=data_update,
#   37=supply_pet, 38=skill_pos_change, 39=special_move

_PET_SYNC_FIELDS = {
    1: ("pet_id", False),
    2: ("hp_change", True),
    3: ("hp_result", True),
    6: ("shield_change", True),
    7: ("shield_result", True),
    8: ("attr_type", False),
    9: ("attr_change", True),
    10: ("attr_result", True),
    11: ("original_damage", True),
    12: ("damage_change", True),
    13: ("damage_result", True),
    14: ("buff_id", False),
    15: ("buff_stack_change", True),
    16: ("buff_stack_result", True),
    17: ("state_bit_change_pos", False),
    25: ("energy_change", True),
    26: ("energy_result", True),
    27: ("state_bit_results", False),
    30: ("instant_kill_change", True),
    31: ("instant_kill_result", True),
    32: ("revive_round", True),
    33: ("revive_rounds", True),
    34: ("charging_skill_id", False),
    35: ("height_change", True),
    36: ("height_result", True),
    38: ("mutation_type", False),
    39: ("max_energy", False),
}

_SKILL_SYNC_FIELDS = {
    1: ("pet_id", False),
    2: ("skill_id", False),
    3: ("damage_param_change", True),
    4: ("damage_param_result", True),
    5: ("cast_cnt_change", True),
    6: ("cast_cnt_result", True),
    7: ("pp_change", True),
    8: ("pp_result", True),
    9: ("cost_energy_change", True),
    10: ("cost_energy_result", True),
    11: ("cost_hp_change", True),
    12: ("cost_hp_result", True),
    13: ("display_hp_result", False),
    14: ("sp_energy_skill", False),
    16: ("damage_param_pet_id", True),
    17: ("state", True),
    18: ("damage_type", True),
}

_ROLE_SYNC_FIELDS = {
    1: ("role_uin", False),
    2: ("role_energy_change", True),
    3: ("role_energy_result", True),
    4: ("item_id", True),
    5: ("remain_use_cnt", True),
    6: ("item_num", True),
    7: ("allow_use_cnt", True),
    8: ("hp_change", True),
    9: ("hp_result", True),
    10: ("pvp_score_change", True),
    11: ("pvp_score_result", True),
    12: ("black_hp_change", True),
    13: ("black_hp_result", True),
    14: ("legend_skill_cast_num", True),
    15: ("allow_use_cnt_inbattle", True),
}

_COMM_SYNC_FIELDS = {
    1: ("sp_energy_type", False),
    2: ("sp_energy_change", True),
    3: ("sp_energy_result", True),
    4: ("final_battle_energy_change", True),
    5: ("final_battle_energy_result", True),
    6: ("b1_phantom_point_change", True),
    7: ("b1_phantom_point_result", True),
}

_ITEM_SYNC_FIELDS = {
    1: ("item_id", False),
    4: ("num", True),
    6: ("remain_use_cnt", True),
    10: ("allow_use_cnt", True),
    11: ("battle_use_time_max", True),
    12: ("battle_use_time_remain", True),
}


def _compact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """丢弃空值，避免把低价值空字段写入状态快照。"""
    return {k: v for k, v in data.items() if v is not None and v != [] and v != {}}


def _pick_sync_value(msg: Dict[str, Any], field_no: int, signed: bool = False) -> Optional[int]:
    value = pick_first(collect_varints(msg, field_no))
    if value is None:
        return None
    return maybe_signed64(value) if signed else value


def _pick_fixed32_float(msg: Dict[str, Any], field_no: int) -> Optional[float]:
    """解析 protobuf wire5 float 字段，服务器会用它同步部分技能换算参数。"""
    for entry in field_groups(msg).get(field_no, []):
        raw = entry.get("raw_hex")
        if not raw:
            continue
        try:
            return round(float(struct.unpack("<f", bytes.fromhex(raw))[0]), 6)
        except (ValueError, struct.error):
            continue
    return None


def _extract_buffdata_93_skill(msg: Dict[str, Any]) -> Dict[str, Any]:
    """解析 triggered_buffs 中的轻量 buff 触发引用。"""
    return _compact_dict({
        "buffbase_id": _pick_sync_value(msg, 1, True),
        "value": _pick_sync_value(msg, 2, True),
        "side": _pick_sync_value(msg, 3, True),
        "role_uin": _pick_sync_value(msg, 4, False),
    })


def _extract_damage_params(msg: Dict[str, Any], field_no: int) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(field_no, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            "pet_id": _pick_sync_value(sub, 1, False),
            "damage_param": _pick_sync_value(sub, 2, False),
        })
        if item:
            items.append(item)
    return items


def _extract_restraint_types(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(27, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            "pet_id": _pick_sync_value(sub, 1, False),
            "restraint_type": _pick_sync_value(sub, 2, True),
        })
        if item:
            items.append(item)
    return items


def _extract_cd_info(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(34, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            "buff_id": _pick_sync_value(sub, 1, False),
            "value": _pick_sync_value(sub, 2, True),
        })
        if item:
            items.append(item)
    return items


def _extract_enhance_info(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(35, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            "buff_id": _pick_sync_value(sub, 1, False),
            "effect_ids": [maybe_signed64(v) for v in collect_varints(sub, 2)],
            "cast_moment": _pick_sync_value(sub, 3, False),
            "tip_id": _pick_sync_value(sub, 4, False),
            "skill_id": normalize_skill_id(_pick_sync_value(sub, 5, False)),
            "stack": _pick_sync_value(sub, 6, False),
            "buffbase_id": _pick_sync_value(sub, 7, False),
            "skill_type": _pick_sync_value(sub, 8, True),
            "caster_pet_base_id": _pick_sync_value(sub, 10, False),
        })
        if item:
            items.append(item)
    return items


def _extract_pet_skill_round_data(msg: Dict[str, Any]) -> Dict[str, Any]:
    """解析 PetSkillRoundData。field 2 是状态，field 3 是类型，field 39 才是技能 ID。"""
    sid = normalize_skill_id(_pick_sync_value(msg, 39, False))
    item = _compact_dict({
        "raw_round_skill_id": _pick_sync_value(msg, 1, False),
        "skill_id": sid,
        "skill_name": skill_name(sid),
        "state": _pick_sync_value(msg, 2, True),
        "type": _pick_sync_value(msg, 3, False),
        "cast_cnt": _pick_sync_value(msg, 4, True),
        "cost_hp": _pick_sync_value(msg, 5, False),
        "display_hp": bool(_pick_sync_value(msg, 6, False) or 0),
        "hp_per_energy": _pick_fixed32_float(msg, 7),
        "last_cast_round": _pick_sync_value(msg, 8, True),
        "cost_energy": _pick_sync_value(msg, 9, False),
        "cost_energy_buff": _pick_sync_value(msg, 10, True),
        "cost_energy_buff_factor": _pick_sync_value(msg, 11, True),
        "cost_energy_buff_mul": _pick_sync_value(msg, 12, True),
        "cost_energy_buff_set": _pick_sync_value(msg, 13, True),
        "sp_energy_skill": _pick_sync_value(msg, 14, False),
        "carryon_slot_idx": _pick_sync_value(msg, 15, True),
        "consume_energy": _pick_sync_value(msg, 16, True),
        "consume_hp": _pick_sync_value(msg, 17, True),
        "ex_damage_param": _pick_sync_value(msg, 18, True),
        "cost_all_energy": bool(_pick_sync_value(msg, 19, False) or 0),
        "fever_state": bool(_pick_sync_value(msg, 20, False) or 0),
        "rule_energy": _pick_sync_value(msg, 21, True),
        "rule_damage_param": _pick_sync_value(msg, 22, True),
        "effect_damage_param": _pick_sync_value(msg, 23, True),
        "buff_damage_param": _pick_sync_value(msg, 24, True),
        "equipped_slot": _pick_sync_value(msg, 25, False),
        "cd_round": _pick_sync_value(msg, 28, True),
        "flag": _pick_sync_value(msg, 29, False),
        "raw_damage": _pick_sync_value(msg, 30, True),
        "used_cnt": _pick_sync_value(msg, 31, False),
        "disable_conf_dam_type": bool(_pick_sync_value(msg, 33, False) or 0),
        "change_times": _pick_sync_value(msg, 36, True),
        "cr_reset_round": _pick_sync_value(msg, 37, True),
        "cr_reset_reason": _pick_sync_value(msg, 38, True),
        "used_cnt_for_evolute": _pick_sync_value(msg, 40, False),
        "change_src_skill": normalize_skill_id(_pick_sync_value(msg, 42, False)),
        "state_tips": _pick_sync_value(msg, 43, False),
        "must_cost_hp": bool(_pick_sync_value(msg, 44, False) or 0),
        "last_pos": _pick_sync_value(msg, 47, False),
        "consume_change_effeciency": _pick_sync_value(msg, 49, False),
        "is_change_effeciency": _pick_sync_value(msg, 50, False),
        "original_pos": _pick_sync_value(msg, 51, False),
        "raw_cost_energy": _pick_sync_value(msg, 52, False),
        "cast_rounds": _pick_sync_value(msg, 53, False),
        "enable_on_charging": bool(_pick_sync_value(msg, 54, False) or 0),
        "round_start_pos": _pick_sync_value(msg, 55, False),
        "last_round_pos": _pick_sync_value(msg, 56, False),
        "swap_from_pet": _pick_sync_value(msg, 57, False),
        "priority_display": bool(_pick_sync_value(msg, 58, False) or 0),
        "perform_flag": _pick_sync_value(msg, 60, False),
        "remove_round": _pick_sync_value(msg, 61, True),
        "original_skill_id": normalize_skill_id(_pick_sync_value(msg, 62, False)),
        "damage_type": _pick_sync_value(msg, 63, True),
        "cost_energy_buff_mul_10000": _pick_sync_value(msg, 64, True),
        "cost_energy_buff_factor_list": [maybe_signed64(v) for v in collect_varints(msg, 65)],
        "cd_outfield_round": _pick_sync_value(msg, 66, True),
        "season_id": _pick_sync_value(msg, 68, True),
        "damage_params": _extract_damage_params(msg, 26),
        "restraint_types": _extract_restraint_types(msg),
        "cd_info": _extract_cd_info(msg),
        "enhance_info": _extract_enhance_info(msg),
    })
    return item


def _extract_skill_change_sync(sync: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(sync).get(5, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        sid = normalize_skill_id(_pick_sync_value(sub, 2, False))
        skill_data = {}
        skill_sub = first_sub(field_groups(sub).get(3, []))
        if skill_sub:
            skill_data = _extract_pet_skill_round_data(skill_sub)
        item = _compact_dict({
            "pet_id": _pick_sync_value(sub, 1, False),
            "skill_id": sid or skill_data.get("skill_id"),
            "skill_name": skill_name(sid or skill_data.get("skill_id")),
            "skill_data": skill_data,
        })
        if item:
            items.append(item)
    return items


def _extract_pet_info_sync(sync: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(sync).get(6, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        common = first_sub(field_groups(sub).get(2, []))
        creature = extract_creature(
            common,
            path="sync_data.pet_info",
            record={"opcode": 0x1324, "opcode_hex": "0x1324"},
        ) if common else None
        compact_skills = []
        for skill in (creature or {}).get("equipped_skills", []):
            compact_skills.append(_compact_dict({
                "skill_id": skill.get("skill_id"),
                "skill_name": skill.get("skill_name"),
                "equipped_slot": skill.get("equipped_slot"),
                "cost_energy": skill.get("cost_energy"),
            }))
        item = _compact_dict({
            "pet_id": (creature or {}).get("pet_id"),
            "name": (creature or {}).get("name"),
            "level": (creature or {}).get("level"),
            "base_conf_id": (creature or {}).get("base_conf_id"),
            "types": (creature or {}).get("types"),
            "max_hp": (creature or {}).get("max_hp"),
            "equipped_skills": compact_skills,
            "data_level": _pick_sync_value(sub, 4, True),
            "full_for_data_level": bool(_pick_sync_value(sub, 5, False) or 0),
        })
        if item:
            items.append(item)
    return items


def _extract_task_infos(sync: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(sync).get(8, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            "task_id": _pick_sync_value(sub, 1, False),
            "task_state": _pick_sync_value(sub, 2, True),
            "uin": _pick_sync_value(sub, 3, False),
        })
        if item:
            items.append(item)
    return items


def _extract_sync_items(sync: Dict[str, Any], field_no: int, spec: Dict[int, tuple]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(sync).get(field_no, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = {
            name: _pick_sync_value(sub, fn, signed)
            for fn, (name, signed) in spec.items()
        }
        if field_no == 3 and item.get("skill_id") is not None:
            sid = normalize_skill_id(item["skill_id"])
            item["skill_id"] = sid
            item["skill_name"] = skill_name(sid)
            item["hp_per_energy"] = _pick_fixed32_float(sub, 15)
        if field_no == 2:
            state_bits = collect_varints(sub, 27)
            if state_bits:
                item["state_bit_results"] = state_bits
            triggered = [
                _extract_buffdata_93_skill(e["sub"])
                for e in field_groups(sub).get(37, [])
                if e.get("sub") is not None
            ]
            triggered = [x for x in triggered if x]
            if triggered:
                item["triggered_buffs"] = triggered
        item = _compact_dict(item)
        if item:
            items.append(item)
    return items


def _extract_pet_skill_updates(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """解析 BattleDataUpdate.pet_skill，补全战斗中的技能运行时数据。"""
    updates: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(7, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        update: Dict[str, Any] = {
            "pet_id": pick_first(collect_varints(sub, 1)),
            "skills": [],
        }
        for skill_entry in field_groups(sub).get(2, []):
            skill_sub = skill_entry.get("sub")
            if skill_sub is None:
                continue
            skill = _extract_pet_skill_round_data(skill_sub)
            if skill:
                update["skills"].append(skill)
        update = _compact_dict(update)
        if update:
            updates.append(update)
    return updates


def _extract_sync_data(sync: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if sync is None:
        return {}
    return _compact_dict({
        "role_sync": _extract_sync_items(sync, 1, _ROLE_SYNC_FIELDS),
        "pet_sync": _extract_sync_items(sync, 2, _PET_SYNC_FIELDS),
        "skill_sync": _extract_sync_items(sync, 3, _SKILL_SYNC_FIELDS),
        "comm_sync": _extract_sync_items(sync, 4, _COMM_SYNC_FIELDS),
        "skill_change_sync": _extract_skill_change_sync(sync),
        "pet_info": _extract_pet_info_sync(sync),
        "item_sync": _extract_sync_items(sync, 7, _ITEM_SYNC_FIELDS),
        "task_infos": _extract_task_infos(sync),
    })


def _attach_perform_meta(out: Dict[str, Any], sub: Dict[str, Any]) -> None:
    """补充 BattlePerformInfo 的通用元信息和同步结果。"""
    is_group_head = pick_first(collect_varints(sub, 11))
    is_last_hit = pick_first(collect_varints(sub, 27))
    out.update({
        "type": pick_first(collect_varints(sub, 1)),
        "index": pick_first(collect_varints(sub, 2)),
        "group_id": pick_first(collect_varints(sub, 2)),
        "is_group_head": bool(is_group_head) if is_group_head is not None else None,
        "phase_arg": pick_first(collect_varints(sub, 14)),
        "cast_moment": pick_first(collect_varints(sub, 14)),
        "state_arg": pick_first(collect_varints(sub, 26)),
        "group_ref": pick_first(collect_varints(sub, 26)),
        "extra_arg": is_last_hit,
        "is_last_hit": bool(is_last_hit) if is_last_hit is not None else None,
        "event_ordinal": pick_first(collect_varints(sub, 39)),
        "exec_index": pick_first(collect_varints(sub, 39)),
    })
    sync_data = _extract_sync_data(first_sub(field_groups(sub).get(12, [])))
    if sync_data:
        out["sync_data"] = sync_data


def _extract_1324_entry(sub: Dict[str, Any]) -> Dict[str, Any]:
    """Extract a single action entry from a 0x1324 sub-message."""
    sg = field_groups(sub)
    entry_type = pick_first(collect_varints(sub, 1))
    out: Dict[str, Any] = {}
    _attach_perform_meta(out, sub)

    if entry_type == 1:
        # skill_cast — skill from field 3, energy from field 12 IR sub
        out["kind"] = "skill_cast"
        out.update(_extract_skill_ref(first_sub(sg.get(3, [])), skill_field=3))
        ir_sub = first_sub(sg.get(12, []))
        detail = first_sub(field_groups(ir_sub).get(2, [])) if ir_sub else None
        if detail:
            rd = pick_first(collect_varints(detail, 25))
            out["energy_delta"] = maybe_signed64(rd) if rd is not None else None
            out["energy_after"] = pick_first(collect_varints(detail, 26), low=0, high=99)

    elif entry_type == 4:
        # damage — BattleDamageInfo from field 6, sync_data from field 12
        out["kind"] = "damage"
        dmg_info = first_sub(sg.get(6, []))
        if dmg_info:
            out.update(_extract_skill_ref(dmg_info, skill_field=3))
            # is_critical (field 5, repeated bool — any nonzero = crit)
            crit_vals = collect_varints(dmg_info, 5)
            out["is_critical"] = any(v != 0 for v in crit_vals) if crit_vals else None
            # restraint_type (field 7): -3..+3 effectiveness indicator
            rt = pick_first(collect_varints(dmg_info, 7))
            out["restraint_type"] = maybe_signed64(rt) if rt is not None else None
            # dam_type (field 9): 1=physical, 2=special
            out["dam_type"] = pick_first(collect_varints(dmg_info, 9))
        dmg_sub = None
        hp_sub = None
        ir = first_sub(sg.get(12, []))
        if ir:
            for child in field_groups(ir).get(2, []):
                cs = child.get("sub")
                if cs is None:
                    continue
                if pick_first(collect_varints(cs, 11)) is not None or pick_first(collect_varints(cs, 13)) is not None:
                    dmg_sub = cs
                elif pick_first(collect_varints(cs, 3)) is not None:
                    hp_sub = cs
        if dmg_sub:
            ro = pick_first(collect_varints(dmg_sub, 12))
            out["damage"] = pick_first(collect_varints(dmg_sub, 11)) or pick_first(collect_varints(dmg_sub, 13))
            out["overflow"] = maybe_signed64(ro) if ro is not None else None
            out["damage_target_side"] = pick_first(collect_varints(dmg_sub, 1))
            out["damage_target_side_name"] = side_name(out.get("damage_target_side"))
        if hp_sub:
            out["target_side"] = pick_first(collect_varints(hp_sub, 1)) or out.get("target_side")
            out["target_side_name"] = side_name(out.get("target_side"))
            out["target_hp_after"] = pick_first(collect_varints(hp_sub, 3), low=0, high=99999)

    elif entry_type == 2:
        # effect_apply — from field 4 sub, related skills from field 12 IR sub
        out["kind"] = "effect_apply"
        em = first_sub(sg.get(4, []))
        if em:
            _extract_actor_target(em, out)
            out["effect_id"] = pick_first(collect_varints(em, 3))
            out["effect_stage"] = pick_first(collect_varints(em, 4))
            _attach_buff_meta(out, out.get("effect_id"))
        ir = first_sub(sg.get(12, []))
        related: List[Dict[str, Any]] = []
        if ir:
            for child in field_groups(ir).get(3, []):
                cs = child.get("sub")
                if not cs:
                    continue
                sx = pick_first(collect_varints(cs, 2), low=100_000)
                rsid = normalize_skill_id(sx)
                owner = pick_first(collect_varints(cs, 1))
                item: Dict[str, Any] = {
                    "owner_side": owner,
                    "owner_side_name": side_name(owner),
                    "skill_id_x100": sx,
                    "skill_id": rsid,
                    "skill_name": skill_name(rsid),
                    "arg3": pick_first(collect_varints(cs, 3)),
                    "arg4": pick_first(collect_varints(cs, 4)),
                }
                _attach_skill_meta(item, rsid)
                related.append(item)
        if related:
            out["related_skills"] = related

    elif entry_type == 3:
        # effect_stage — from field 5 sub
        out["kind"] = "effect_stage"
        em = first_sub(sg.get(5, []))
        if em:
            _extract_actor_target(em, out)
            out["effect_id"] = pick_first(collect_varints(em, 3))
            out["effect_base"] = pick_first(collect_varints(em, 6))
            _attach_buff_meta(out, out.get("effect_id"))
            _attach_buffbase_meta(out, out.get("effect_base"))

    elif entry_type == 7:
        # defeat — from field 9 sub
        out["kind"] = "defeat"
        dm = first_sub(sg.get(9, []))
        if dm:
            _extract_actor_target(dm, out)
            out["defeat_arg"] = pick_first(collect_varints(dm, 3))

    elif entry_type == 10:
        # effect_link — from field 15 sub
        out["kind"] = "effect_link"
        lm = first_sub(sg.get(15, []))
        if lm:
            _extract_actor_target(lm, out)
            out["effect_id"] = pick_first(collect_varints(lm, 3))
            _attach_buff_meta(out, out.get("effect_id"))

    elif entry_type == 5:
        # BPT_HEAL — from field 7 sub (BattleHealInfo)
        out["kind"] = "heal"
        hm = first_sub(sg.get(7, []))
        if hm:
            _extract_actor_target(hm, out)
            out["heal_type"] = pick_first(collect_varints(hm, 4))
            out["source_id"] = pick_first(collect_varints(hm, 3))
        ir = first_sub(sg.get(12, []))
        if ir:
            for child in field_groups(ir).get(2, []):
                cs = child.get("sub")
                if cs is None:
                    continue
                hp = pick_first(collect_varints(cs, 3), low=0, high=99999)
                if hp is not None:
                    out["target_hp_after"] = hp
                    break

    elif entry_type == 6:
        # BPT_ENERGY — from field 8 sub (BattleEnergyInfo)
        out["kind"] = "energy"
        em = first_sub(sg.get(8, []))
        if em:
            _extract_actor_target(em, out)
            out["source_id"] = pick_first(collect_varints(em, 3))
        ir = first_sub(sg.get(12, []))
        if ir:
            for child in field_groups(ir).get(2, []):
                cs = child.get("sub")
                if cs is None:
                    continue
                rd = pick_first(collect_varints(cs, 25))
                ea = pick_first(collect_varints(cs, 26), low=0, high=99)
                if rd is not None or ea is not None:
                    out["energy_delta"] = maybe_signed64(rd) if rd is not None else None
                    out["energy_after"] = ea
                    break

    elif entry_type == 8:
        # BPT_REVIVE — from field 10 sub (BattleReviveInfo)
        out["kind"] = "revive"
        rm = first_sub(sg.get(10, []))
        if rm:
            _extract_actor_target(rm, out)

    elif entry_type == 9:
        # BPT_EFFECT_TRIGGER — from field 13 sub (BattleEffectTrigger)
        out["kind"] = "effect_trigger"
        em = first_sub(sg.get(13, []))
        if em:
            _extract_actor_target(em, out)
            out["effect_id"] = pick_first(collect_varints(em, 3))
            out["trigger_result"] = pick_first(collect_varints(em, 5))
            out["trigger_params"] = collect_varints(em, 6)
            _attach_buff_meta(out, out.get("effect_id"))

    elif entry_type == 11:
        # BPT_SP_ENERGY_CHANGE — from field 17 sub (BattleSpEnergyChange)
        out["kind"] = "sp_energy_change"
        em = first_sub(sg.get(17, []))
        if em:
            out["sp_change_type"] = pick_first(collect_varints(em, 1))
            ele_sub = first_sub(field_groups(em).get(2, []))
            if ele_sub:
                out["sp_element"] = {
                    "dam_type": pick_first(collect_varints(ele_sub, 1)),
                    "stack": pick_first(collect_varints(ele_sub, 2)),
                }
            out["sp_change_src"] = pick_first(collect_varints(em, 3))
            out["caster_id"] = pick_first(collect_varints(em, 4))
            out["target_id"] = pick_first(collect_varints(em, 5))
            cv = pick_first(collect_varints(em, 6))
            rv = pick_first(collect_varints(em, 7))
            out["change_value"] = maybe_signed64(cv) if cv is not None else None
            out["real_change_value"] = maybe_signed64(rv) if rv is not None else None

    elif entry_type == 12:
        # BPT_SP_ENERGY_TRIGGER — from field 16 sub (BattleSpEnergyTrigger)
        out["kind"] = "sp_energy_trigger"
        em = first_sub(sg.get(16, []))
        if em:
            out["dam_type"] = pick_first(collect_varints(em, 1))
            out["trigger_type"] = pick_first(collect_varints(em, 2))
            out["caster_id"] = pick_first(collect_varints(em, 3))
            old_raw = pick_first(collect_varints(em, 4))
            new_raw = pick_first(collect_varints(em, 5))
            out["old_skill_id"] = normalize_skill_id(old_raw) if old_raw else None
            out["old_skill_name"] = skill_name(out["old_skill_id"]) if out["old_skill_id"] else None
            out["new_skill_id"] = normalize_skill_id(new_raw) if new_raw else None
            out["new_skill_name"] = skill_name(out["new_skill_id"]) if out["new_skill_id"] else None

    elif entry_type == 13:
        # BPT_CHANGE_PET — from field 18 sub (BattleChangePet)
        out["kind"] = "change_pet"
        cm = first_sub(sg.get(18, []))
        if cm:
            _extract_actor_target(cm, out)
            out["rest_pet_id"] = pick_first(collect_varints(cm, 2))
            out["battle_pet_id"] = pick_first(collect_varints(cm, 3))
            out["is_cmd"] = pick_first(collect_varints(cm, 5))
            # BattlePetInfo in field 4 → contains the entering pet's data
            # field 4 → sub has field 1 (pet state) and field 2 (pet info)
            # Both describe the NEW (entering) pet, not the rest pet
            pet_wrapper = first_sub(field_groups(cm).get(4, []))
            if pet_wrapper:
                pwg = field_groups(pet_wrapper)
                # pet_info sub (field 2 of wrapper): pet_id at f2, name at f3
                info_sub = first_sub(pwg.get(2, []))
                if info_sub:
                    out["new_pet_id"] = pick_first(collect_varints(info_sub, 2), low=1)
                    out["new_pet_name"] = first_text(info_sub, 3)
                    out["new_pet_types"] = [SDT_TO_TYPE.get(v, v) for v in collect_varints(info_sub, 6)]
                    out["new_pet_level"] = pick_first(collect_varints(info_sub, 10), low=1, high=100)
                    out["new_pet_base_conf_id"] = pick_first(collect_varints(info_sub, 15))
                # pet_state sub (field 1 of wrapper) = BattleInsidePetInfo
                state_sub = first_sub(pwg.get(1, []))
                if state_sub:
                    # Fallback pet_id/name if not found in info_sub
                    if not out.get("new_pet_name"):
                        out["new_pet_id"] = pick_first(collect_varints(state_sub, 21), low=1)
                        out["new_pet_name"] = first_text(state_sub, 23)
                    # Extract battle stats: field 6 = [HP, ATK, DEF, SPA, SPD, SPE]
                    ds = collect_varints(state_sub, 6)
                    if len(ds) >= 7:
                        out["new_pet_battle_stats"] = ds[1:7]
                    # current_hp from battle_attr[25]
                    if len(ds) >= 26:
                        out["new_pet_current_hp"] = ds[25]
                        out["new_pet_max_hp"] = ds[1]
                    # 能量来自 PetData.field 33（info_sub = PetData）
                    # battle_attr[26] 是"宠物伤害类型1"，不是能量。
                    raw_pet_energy = pick_first(collect_varints(info_sub, 33)) if info_sub else None
                    if raw_pet_energy is not None and raw_pet_energy > 0:
                        out["new_pet_energy"] = raw_pet_energy
                    # passive_skill_id from field 64
                    out["new_pet_passive_skill_id"] = pick_first(collect_varints(state_sub, 64))

    elif entry_type == 15:
        # BPT_IDLE — from field 20 sub (BattleIdleInfo)
        out["kind"] = "idle"
        im = first_sub(sg.get(20, []))
        if im:
            out["idle_pet_id"] = pick_first(collect_varints(im, 1))

    elif entry_type == 19:
        # BPT_SKILL_STATE — from field 24 sub (BattleSkillStateInfo)
        out["kind"] = "skill_state"
        sm = first_sub(sg.get(24, []))
        if sm:
            out["caster_pet_id"] = pick_first(collect_varints(sm, 1))
            out["state_code"] = pick_first(collect_varints(sm, 2))

    elif entry_type == 22:
        # BPT_WEATHER_CHANGE — from field 29 sub (BattleWeatherChange)
        out["kind"] = "weather_change"
        wm = first_sub(sg.get(29, []))
        if wm:
            out["skill_id"] = pick_first(collect_varints(wm, 1))
            out["skill_name"] = skill_name(out["skill_id"])
            out["weather_id"] = pick_first(collect_varints(wm, 2))
            out["weather_name"] = _weather_name(out["weather_id"])
            out["expire_round"] = pick_first(collect_varints(wm, 5))

    elif entry_type == 23:
        # BPT_NOTIFY_PERFORM — from field 30 sub (BattleNotifyPerform)
        out["kind"] = "notify_perform"
        nm = first_sub(sg.get(30, []))
        if nm:
            out["notify_type"] = pick_first(collect_varints(nm, 1))
            out["notify_data"] = collect_varints(nm, 2)
            out["tips_id"] = first_text(nm, 3)
            params = [e.get("text", "") for e in field_groups(nm).get(4, []) if e.get("text")]
            if params:
                out["params"] = params
            out["uin"] = pick_first(collect_varints(nm, 5))

    elif entry_type == 24:
        # BPT_CHANGE_MODEL - from field 32 sub (BattleChangeModel)
        out["kind"] = "change_model"
        cm = first_sub(sg.get(32, []))
        if cm:
            pet_id = pick_first(collect_varints(cm, 1))
            out["pet_id"] = pet_id
            out["actor_side"] = pet_id
            out["actor_side_name"] = side_name(pet_id)
            out["target_side"] = pet_id
            out["target_side_name"] = side_name(pet_id)
            out["old_base_id"] = pick_first(collect_varints(cm, 2))
            out["role_magic_flag"] = pick_first(collect_varints(cm, 4))

            pet_wrapper = first_sub(field_groups(cm).get(3, []))
            if pet_wrapper:
                pwg = field_groups(pet_wrapper)
                state_sub = first_sub(pwg.get(1, []))
                if state_sub:
                    out["model_pet_id"] = pick_first(collect_varints(state_sub, 21), low=1)
                    out["model_base_id"] = pick_first(collect_varints(state_sub, 22), low=1)
                    out["model_pet_name"] = first_text(state_sub, 23)
                    ds = collect_varints(state_sub, 6)
                    if len(ds) >= 7:
                        out["model_battle_stats"] = ds[1:7]
                    if len(ds) >= 26:
                        out["model_current_hp"] = ds[25]
                        out["model_max_hp"] = ds[1]

                info_sub = first_sub(pwg.get(2, []))
                if info_sub:
                    out["original_pet_id"] = pick_first(collect_varints(info_sub, 2), low=1)
                    out["original_pet_name"] = first_text(info_sub, 3)
                    out["original_pet_types"] = [SDT_TO_TYPE.get(v, v) for v in collect_varints(info_sub, 6)]
                    out["original_pet_level"] = pick_first(collect_varints(info_sub, 10), low=1, high=100)
                    out["original_base_conf_id"] = pick_first(collect_varints(info_sub, 15))

    elif entry_type == 29:
        # BPT_ROLE_SKILL_CAST — from field 37 sub (BattleRoleSkillCast)
        out["kind"] = "role_skill_cast"
        rm = first_sub(sg.get(37, []))
        if rm:
            out["caster_uin"] = pick_first(collect_varints(rm, 1))
            skill_raw = pick_first(collect_varints(rm, 2))
            sid = normalize_skill_id(skill_raw) if skill_raw else None
            out["skill_id"] = sid
            out["skill_name"] = skill_name(sid) if sid else None
            if sid:
                _attach_skill_meta(out, sid)
            out["pet_id"] = pick_first(collect_varints(rm, 3))
            out["is_call_success"] = bool(pick_first(collect_varints(rm, 4)) or 0)

    elif entry_type == 30:
        # BPT_COMBO_SKILL — from field 38 sub (BattleComboSkillCast)
        out["kind"] = "combo_skill_cast"
        cm = first_sub(sg.get(38, []))
        if cm:
            _extract_actor_target(cm, out)
            out["caster_id"] = pick_first(collect_varints(cm, 1))
            out["target_id"] = collect_varints(cm, 2)
            skill_id_x100 = pick_first(collect_varints(cm, 3), low=100_000)
            sid = normalize_skill_id(skill_id_x100)
            out["skill_id_x100"] = skill_id_x100
            out["skill_id"] = sid
            out["skill_name"] = skill_name(sid)
            _attach_skill_meta(out, sid)
            out["combo_index"] = pick_first(collect_varints(cm, 8))
            out["combo_count"] = pick_first(collect_varints(cm, 9))

    elif entry_type == 25:
        # BPT_AI — from field 33 sub (BattleAIPerform)
        out["kind"] = "ai_action"
        am = first_sub(sg.get(33, []))
        if am:
            out["pet_id"] = pick_first(collect_varints(am, 1))
            out["uin"] = pick_first(collect_varints(am, 2))
            out["ai_type"] = pick_first(collect_varints(am, 3))
            out["param"] = pick_first(collect_varints(am, 4))

    elif entry_type == 34:
        # BPT_BATTLER_PVP_PERFORM — from field 43 sub (BattlerPvpPerform)
        out["kind"] = "pvp_perform_marker"
        pm = first_sub(sg.get(43, []))
        if pm:
            out["uin"] = pick_first(collect_varints(pm, 1))
            out["pvp_type"] = pick_first(collect_varints(pm, 2))

    elif entry_type == 35:
        # BPT_DATA_UPDATE — from field 44 sub (BattleDataUpdate)
        out["kind"] = "data_update"
        dm = first_sub(sg.get(44, []))
        if dm:
            out["uin"] = pick_first(collect_varints(dm, 1))
            pet_sub = first_sub(field_groups(dm).get(3, []))
            if pet_sub:
                out["pet_id"] = pick_first(collect_varints(pet_sub, 1))
            pet_skill_updates = _extract_pet_skill_updates(dm)
            if pet_skill_updates:
                out["pet_skill_updates"] = pet_skill_updates

    elif entry_type == 37:
        # BPT_SUPPLY_PET — from field 45 sub (BattleSupplyPetPlayerInfo)
        out["kind"] = "supply_pet"
        sm = first_sub(sg.get(45, []))
        if sm:
            out["player_id"] = pick_first(collect_varints(sm, 1))
            pet_infos = []
            for child in field_groups(sm).get(2, []):
                cs = child.get("sub")
                if cs is None:
                    continue
                pet_infos.append({
                    "pet_id": pick_first(collect_varints(cs, 1)),
                    "pet_pos": pick_first(collect_varints(cs, 2)),
                })
            if pet_infos:
                out["supply_pets"] = pet_infos

    elif entry_type == 38:
        # BPT_SKILL_POS_CHANGE — from field 46 sub (BattleSkillPosChange)
        out["kind"] = "skill_pos_change"
        cm = first_sub(sg.get(46, []))
        if cm:
            out["pet_id"] = pick_first(collect_varints(cm, 1))
            pos_infos = []
            for child in field_groups(cm).get(2, []):
                cs = child.get("sub")
                if cs is None:
                    continue
                info = {
                    "skill_id": pick_first(collect_varints(cs, 1)),
                    "old_pos": pick_first(collect_varints(cs, 2)),
                    "new_pos": pick_first(collect_varints(cs, 3)),
                    "change_type": pick_first(collect_varints(cs, 4)),
                }
                if info["skill_id"]:
                    info["skill_name"] = skill_name(info["skill_id"])
                pos_infos.append(info)
            if pos_infos:
                out["skill_pos_infos"] = pos_infos

    elif entry_type == 39:
        # BPT_SPECIAL_MOVE — from field 47 sub (BattleSpecialMoveInfo)
        out["kind"] = "special_move"
        sm = first_sub(sg.get(47, []))
        if sm:
            out["pet_id"] = pick_first(collect_varints(sm, 1))
            out["special_move_id"] = pick_first(collect_varints(sm, 2))
            out["special_move_type"] = pick_first(collect_varints(sm, 3))
            out["round"] = pick_first(collect_varints(sm, 4))
            skill_raw = pick_first(collect_varints(sm, 5))
            sid = normalize_skill_id(skill_raw) if skill_raw else None
            out["skill_id"] = sid
            out["skill_name"] = skill_name(sid) if sid else None

    else:
        out["kind"] = f"unknown_type_{entry_type}"

    return out


def _extract_perform_cmd(container: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all entries from a perform-command container and build a summary."""
    c_groups = field_groups(container)

    packet_state = pick_first(collect_varints(container, 1))
    packet_phase = pick_first(collect_varints(container, 3))
    packet_index = pick_first(collect_varints(container, 5))

    entries: List[Dict[str, Any]] = []
    for f2_entry in c_groups.get(2, []):
        sub = f2_entry.get("sub")
        if sub is not None:
            entries.append(_extract_1324_entry(sub))

    effect_ids = sorted({int(it["effect_id"]) for it in entries if it.get("effect_id") is not None})
    effect_names = [buff_name(eid) or str(eid) for eid in effect_ids]

    out: Dict[str, Any] = {
        "packet_state": packet_state,
        "packet_phase": packet_phase,
        "packet_index": packet_index,
        "entries": entries,
        "primary_skill": next((it for it in entries if it.get("skill_id")), None),
        "energy_event": next((it for it in entries if it.get("kind") == "skill_cast"), None),
        "damage_event": next((it for it in entries if it.get("kind") == "damage"), None),
        "effect_ids": effect_ids,
        "effect_names": effect_names,
        "has_defeat": any(it.get("kind") == "defeat" for it in entries),
        "opcode": record.get("opcode"),
        "opcode_hex": record.get("opcode_hex", ""),
    }
    return out


def extract_1324_action(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract action details from opcode 0x1324."""
    root = record.get("root")
    if root is None:
        return None

    groups = field_groups(root)
    container_entries = groups.get(1, [])
    container = first_sub(container_entries)
    if container is None:
        return None

    result = _extract_perform_cmd(container, record)
    result["extract_kind"] = "action"
    return result


# ---------------------------------------------------------------------------
# 0x13f4 - Refresh
# ---------------------------------------------------------------------------

def extract_13f4_refresh(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract refresh / energy info from opcode 0x13F4."""
    root = record.get("root")
    if root is None:
        return None

    container = first_sub(field_groups(root).get(1, []))
    if container is None:
        return None

    cg = field_groups(container)
    detail: Dict[str, Any] = {
        "packet_state": pick_first(collect_varints(container, 1)),
        "packet_phase": pick_first(collect_varints(container, 3)),
        "packet_index": pick_first(collect_varints(container, 5)),
        "skill_options": [],
    }

    for entry in cg.get(2, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        et = pick_first(collect_varints(sub, 1))

        if et == 14:
            meta = first_sub(field_groups(sub).get(19, []))
            if meta:
                detail["battle_token"] = pick_first(collect_varints(meta, 1), low=100_000)
                for i in range(2, 6):
                    detail[f"arg{i}"] = pick_first(collect_varints(meta, i))
            or_ = first_sub(field_groups(sub).get(12, []))
            if or_:
                for se in field_groups(or_).get(3, []):
                    ss = se.get("sub")
                    if not ss:
                        continue
                    sx = pick_first(collect_varints(ss, 2), low=100_000)
                    sid = normalize_skill_id(sx)
                    if sid:
                        detail["skill_options"].append({
                            "skill_id_x100": sx,
                            "skill_id": sid,
                            "skill_name": skill_name(sid),
                            "slot": pick_first(collect_varints(ss, 10), low=0, high=20),
                        })

        elif et == 6:
            ir = first_sub(field_groups(sub).get(12, []))
            info = first_sub(field_groups(ir).get(2, [])) if ir else None
            if info:
                rd = pick_first(collect_varints(info, 25))
                detail["energy_delta"] = maybe_signed64(rd) if rd is not None else None
                detail["energy_after"] = pick_first(collect_varints(info, 26), low=0, high=99)

    detail["skill_options"].sort(
        key=lambda it: (it.get("slot") is None, int(it.get("slot") or 0), int(it.get("skill_id") or 0))
    )

    if not detail["skill_options"] and detail.get("energy_delta") is None and detail.get("energy_after") is None:
        return None

    if detail.get("energy_after") == _ENERGY_BOTTLE_MAX and (detail.get("energy_delta") or 0) > 0:
        detail["action_name"] = "能量瓶"
        detail["kind"] = "energy_bottle"

    detail["opcode"] = record.get("opcode")
    detail["opcode_hex"] = record.get("opcode_hex", "")
    return detail


# ---------------------------------------------------------------------------
# 0x0102 - Creatures
# ---------------------------------------------------------------------------

def extract_0102_creatures(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract creature list from opcode 0x0102 using RKPP's root.2[*].4[*] path."""
    root = record.get("root")
    if root is None:
        return []

    out: List[Dict[str, Any]] = []
    for outer in field_groups(root).get(2, []):
        os_ = outer.get("sub")
        if os_ is None:
            continue
        for re_ in field_groups(os_).get(4, []):
            rh = re_.get("raw_hex")
            if not rh:
                continue
            blob = bytes.fromhex(rh)
            off = 0
            while off < len(blob):
                try:
                    tag, off = read_varint(blob, off)
                    length, off = read_varint(blob, off)
                except ValueError:
                    break
                fn, wt = tag >> 3, tag & 7
                if fn != 1 or wt != 2 or off + length > len(blob):
                    break
                eb = blob[off:off + length]
                off += length
                c = extract_creature(
                    parse_proto_message(eb),
                    path="root.2[*].4[*].1[*]",
                    record=record,
                )
                if c and c.get("slot") not in (None, 0):
                    out.append(c)

    dedup: Dict[int, Dict[str, Any]] = {}
    for c in out:
        s = c.get("slot")
        if s is not None:
            dedup[int(s)] = c
    return [dedup[s] for s in sorted(dedup)]


# ---------------------------------------------------------------------------
# 0x0102 - Metadata
# ---------------------------------------------------------------------------

def extract_0102_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract player metadata from opcode 0x0102."""
    root = record.get("root")
    if root is None:
        return {}

    groups = field_groups(root)
    out: Dict[str, Any] = {}

    # Player info from nested fields
    for entry in groups.get(1, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        sub_groups = field_groups(sub)
        user_id = pick_first(collect_varints(sub, 1))
        uin = pick_first(collect_varints(sub, 2))
        nickname = first_text(sub, 3)
        if user_id is not None:
            out["user_id"] = user_id
        if uin is not None:
            out["uin"] = uin
        if nickname is not None:
            out["nickname"] = nickname

    # Config / pet info from field 3
    for entry in groups.get(3, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        sub_groups = field_groups(sub)
        pet_ids = collect_varints(sub, 1)
        active_pet_id = pick_first(collect_varints(sub, 2))
        if pet_ids:
            out["pet_ids"] = pet_ids
        if active_pet_id is not None:
            out["active_pet_id"] = active_pet_id

    return out


# ---------------------------------------------------------------------------
# 0x0220 - Handle
# ---------------------------------------------------------------------------

def extract_0220_handle(record: Dict[str, Any]) -> Optional[int]:
    """Extract handle value from opcode 0x0220."""
    root = record.get("root")
    if root is None:
        return None

    groups = field_groups(root)
    # Navigate nested fields: typically field 2 -> sub -> field 1
    for entry in groups.get(2, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        handle = pick_first(collect_varints(sub, 1))
        if handle is not None:
            return handle
        # Try deeper nesting
        sub_groups = field_groups(sub)
        for inner in sub_groups.get(2, []):
            inner_sub = inner.get("sub")
            if inner_sub is None:
                continue
            handle = pick_first(collect_varints(inner_sub, 1))
            if handle is not None:
                return handle

    # Fallback: try field 1 directly
    handle = pick_first(collect_varints(root, 1))
    return handle


# ---------------------------------------------------------------------------
# 0x01a9 - Action (candidate selection)
# ---------------------------------------------------------------------------

def extract_01a9_action(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract action-candidate info from opcode 0x01A9."""
    out: Dict[str, Any] = {"candidate_ids": []}

    root = record.get("root")
    if root is None:
        return out

    for oe in field_groups(root).get(4, []):
        outer = oe.get("sub")
        if outer is None:
            continue
        pe = next((e for e in field_groups(outer).get(2, []) if e.get("sub")), None)
        if pe is None:
            continue
        payload = pe["sub"]
        ids: List[int] = []
        for fn in (1, 2, 3):
            item = next((e for e in field_groups(payload).get(fn, []) if e.get("sub")), None)
            if item:
                for f in (1, 2, 3):
                    ids.extend(collect_varints(item["sub"], f))
        out.update({
            "candidate_ids": [int(v) for v in ids],
            "actor_token": pick_first(collect_varints(outer, 1)),
            "raw_kind": pick_first(collect_varints(outer, 4)),
        })
        if ids:
            out["primary_id"] = int(ids[0])
            break

    return out


# ---------------------------------------------------------------------------
# 0x1316 - Battle enter
# ---------------------------------------------------------------------------

def extract_1316_enter(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract battle-enter details from opcode 0x1316."""

    # Schema-first
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

    # Raw fallback
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


# ---------------------------------------------------------------------------
# 0x131a - Round start
# ---------------------------------------------------------------------------

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

    # Raw fallback
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


# ---------------------------------------------------------------------------
# 0x132c - Finish
# ---------------------------------------------------------------------------

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

    # Raw fallback
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
    for e in rg.get(8, []):
        sub = e.get("sub")
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


# ---------------------------------------------------------------------------
# 0x13fc - PVP perform
# ---------------------------------------------------------------------------

def extract_13fc_pvp_perform(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract PVP perform details from opcode 0x13FC (same structure as 0x1324)."""
    root = record.get("root")
    if root is None:
        return None

    groups = field_groups(root)
    container_entries = groups.get(1, [])
    container = first_sub(container_entries)
    if container is None:
        return None

    result = _extract_perform_cmd(container, record)
    result["extract_kind"] = "pvp_perform"
    return result


# ---------------------------------------------------------------------------
# 0x13f3 - Preplay
# ---------------------------------------------------------------------------

def extract_13f3_preplay(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract preplay details from opcode 0x13F3 (same structure as 0x1324)."""
    root = record.get("root")
    if root is None:
        return None

    groups = field_groups(root)
    container_entries = groups.get(1, [])
    container = first_sub(container_entries)
    if container is None:
        return None

    result = _extract_perform_cmd(container, record)
    result["extract_kind"] = "preplay"
    return result


# ---------------------------------------------------------------------------
# 0x1312 - Round flow
# ---------------------------------------------------------------------------

def extract_1312_round_flow(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract round-flow details from opcode 0x1312."""
    out: Dict[str, Any] = {"extract_kind": "round_flow"}

    # Schema-first
    payload = _schema_payload(record, "ZoneBattleRoundFlowNotify")
    if payload is not None:
        # Dump all schema fields
        for key, value in payload.items():
            if key not in out:
                out[key] = value
        _schema_quality(out, message="ZoneBattleRoundFlowNotify", found=True)
    else:
        # Fallback: generic field dump
        root = record.get("root")
        if root is not None:
            groups = field_groups(root)
            for field_no in sorted(groups.keys()):
                entries = groups[field_no]
                values = collect_varints(root, field_no)
                if values:
                    out[f"field_{field_no}_varints"] = values
                for e in entries:
                    if e.get("text"):
                        out[f"field_{field_no}_text"] = e["text"]
                        break
        _schema_quality(out, message="ZoneBattleRoundFlowNotify", found=False)

    # State wrappers
    wrappers = extract_state_wrappers_from_record(record)
    if wrappers:
        out["wrappers"] = wrappers

    out["opcode"] = record.get("opcode")
    out["opcode_hex"] = record.get("opcode_hex", "")
    return out


# ---------------------------------------------------------------------------
# Auxiliary battle opcodes (0x1326, 0x132A, 0x132D, 0x1334, 0x133C, 0x13F6)
# ---------------------------------------------------------------------------

def _schema_or_raw(record: Dict[str, Any], message_name: str) -> Dict[str, Any]:
    """Return schema-decoded dict or raw field dump."""
    decoded = _schema_payload(record, message_name)
    if decoded is not None:
        return dict(decoded)
    root = record.get("root")
    if root is None:
        return {}
    out: Dict[str, Any] = {}
    for fn, entries in field_groups(root).items():
        vals = collect_varints(root, fn)
        if vals:
            out[f"field_{fn}"] = vals[0] if len(vals) == 1 else vals
        for e in entries:
            if e.get("text"):
                out[f"field_{fn}_text"] = e["text"]
                break
    return out


def _make_simple_extractor(message_name: str):
    """生成标准的 auxiliary extractor: schema_or_raw + opcode 标记。"""
    def _extractor(record: Dict[str, Any]) -> Dict[str, Any]:
        detail = _schema_or_raw(record, message_name)
        detail["opcode"] = record.get("opcode")
        detail["opcode_hex"] = record.get("opcode_hex", "")
        return detail
    return _extractor


extract_1326_auto_cmd = _make_simple_extractor("ChangeAutoCmdNotify")
extract_1326_auto_cmd.__doc__ = """0x1326 ChangeAutoCmdNotify — auto battle toggle."""

extract_132a_role_leave = _make_simple_extractor("RoleLeaveNotify")
extract_132a_role_leave.__doc__ = """0x132A RoleLeaveNotify — player disconnect."""

extract_132d_force_finish = _make_simple_extractor("BattleForceFinishNotify")
extract_132d_force_finish.__doc__ = """0x132D BattleForceFinishNotify — forced battle end."""

extract_1334_emoji = _make_simple_extractor("EmojiNotify")
extract_1334_emoji.__doc__ = """0x1334 EmojiNotify — battle emote."""

extract_133c_catch_rsp = _make_simple_extractor("CatchConfirmRsp")
extract_133c_catch_rsp.__doc__ = """0x133C CatchConfirmRsp — capture result."""

extract_13f6_ai_skill = _make_simple_extractor("AiSelectSkillNotify")
extract_13f6_ai_skill.__doc__ = """0x13F6 AiSelectSkillNotify — AI skill hint."""


# ---------------------------------------------------------------------------
# Round confirm opcodes (0x1313, 0x1314)
# ---------------------------------------------------------------------------

def _raw_field_dump(record: Dict[str, Any]) -> Dict[str, Any]:
    """通用 raw 字段转储，提取所有 varint 字段。"""
    root = record.get("root")
    detail: Dict[str, Any] = {}
    if root is not None:
        for fn, entries in field_groups(root).items():
            vals = collect_varints(root, fn)
            if vals:
                detail[f"field_{fn}"] = vals[0] if len(vals) == 1 else vals
    detail["opcode"] = record.get("opcode")
    detail["opcode_hex"] = record.get("opcode_hex", "")
    return detail


def extract_1313_round_confirm(record: Dict[str, Any]) -> Dict[str, Any]:
    """0x1313 BattleRoundConfirmNotify — round confirm."""
    return _raw_field_dump(record)


def extract_1314_round_confirm_rsp(record: Dict[str, Any]) -> Dict[str, Any]:
    """0x1314 BattleRoundConfirmRsp — round confirm response."""
    return _raw_field_dump(record)
