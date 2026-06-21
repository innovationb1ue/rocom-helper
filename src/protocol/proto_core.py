"""核心协议解析兼容门面。

底层 protobuf/TGCP 解析、名称查找、宠物提取和 state wrapper 提取已拆到
``src.protocol.proto`` 子模块；本文件保留历史导入路径，避免影响协议解析、
回放和 WebSocket 管线的现有调用方。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.protocol.proto.constants import (
    SDT_TO_TYPE,
    SIDE_NAMES,
    SPECIAL_ACTION_COMMANDS,
    SPECIAL_ACTION_SHAPES,
    STAT_NAMES,
    _ENERGY_BOTTLE_MAX,
    _WILLPOWER_SKILL_ID,
)
from src.protocol.proto.creature import (
    _attach_skill_meta,
    extract_battle_buffs,
    extract_creature,
    extract_simple_items as _extract_simple_items,
    extract_skills,
    extract_skills_from_round_data,
    extract_stats,
)
from src.protocol.proto.lookups import (
    _attach_buff_meta,
    _attach_buffbase_meta,
    _extract_actor_target,
    buff_name,
    normalize_skill_id,
    pet_name_fn,
    side_name,
    skill_name,
    type_name,
)
from src.protocol.proto.schema import decode_proto_by_schema
from src.protocol.proto.state_wrapper import (
    _side_from_path,
    dedupe_state_wrappers as _dedupe_state_wrappers,
    extract_state_wrapper,
    extract_state_wrappers_from_record,
)
from src.protocol.proto.transport import (
    SSTOP_CODE_NAMES,
    TGCP_COMMAND_NAMES,
    parse_record,
    parse_special_payload,
    parse_tgcp_control_packet,
    tgcp_command_name,
)
from src.protocol.proto.tree import (
    collect_varints,
    field_groups,
    first_sub,
    first_text,
    pick_first,
    walk_messages,
)
from src.protocol.proto.wire import (
    maybe_signed64,
    maybe_utf8,
    normalize_c2s_opcode,
    parse_proto_message,
    read_varint,
    strip_tsf4g_padding,
    tsf4g_trailer_len,
)


def extract_inner_message(root: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not root.get("fields"):
        return None
    fs = root["fields"][0].get("sub")
    if fs is None or len(fs["fields"]) != 1:
        return None
    wrapper = fs["fields"][0]
    ws = wrapper.get("sub")
    if ws is None:
        return None
    return {"message_id": wrapper["field"], "fields": {"fields": ws["fields"]}}
