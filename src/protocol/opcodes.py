"""操作码注册与消息分发模块。

使用装饰器模式构建两个注册表：
- _OPCODE_REGISTRY: 主操作码 → (kind, handler) 映射
- _INNER_REGISTRY: 内嵌消息ID → (kind, handler) 映射（仅用于 opcode 0x0414）

summarize() 是公开的分发入口：
  - opcode 0x0414 + inner payload → 查 _INNER_REGISTRY
  - 其他 opcode → 查 _OPCODE_REGISTRY
  - 未命中 → 查 opcode_pb_map.json 元数据
  - 兜底 → ("unknown", {opcode})
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from src.protocol.inner_messages import (
    parse_inner1_detail,
    parse_inner51_detail,
    parse_inner200_detail,
    parse_inner390_detail,
)
from src.protocol.battle import (
    extract_0102_creatures,
    extract_0102_metadata,
    extract_130b_skill_select,
    extract_1322_skill_declare,
    extract_130c_result,
    extract_1324_action,
    extract_13f4_refresh,
    extract_1316_enter,
    extract_131a_round_start,
    extract_132c_finish,
    extract_13fc_pvp_perform,
    extract_13f3_preplay,
    extract_1312_round_flow,
    extract_01a9_action,
    extract_0220_handle,
    extract_1326_auto_cmd,
    extract_132a_role_leave,
    extract_132d_force_finish,
    extract_1334_emoji,
    extract_133c_catch_rsp,
    extract_13f6_ai_skill,
    extract_1313_round_confirm,
    extract_1314_round_confirm_rsp,
    extract_1305_load_finish_req,
    extract_1306_load_finish_rsp,
    extract_1309_supply_pet_req,
    extract_130a_supply_pet_rsp,
    extract_132e_player_runaway_req,
    extract_132f_player_runaway_rsp,
    extract_1335_round_op_query_req,
    extract_1336_round_op_query_rsp,
    extract_13f9_pk_again,
)
from src.protocol.opcode_dispatch import summarize_record
from src.protocol.opcode_registry import (
    INNER_REGISTRY as _INNER_REGISTRY,
    OPCODE_REGISTRY as _OPCODE_REGISTRY,
    make_detail_handler as _make_detail_handler,
    register_inner as _register_inner,
    register_opcode as _register_opcode,
)


# ---------------------------------------------------------------------------
# Opcode handlers
# ---------------------------------------------------------------------------


# Special handlers with non-standard return shapes
@_register_opcode(0x0102, "roster_init")
def _handle_0102(record, inner) -> Dict[str, Any]:
    return {
        "metadata": extract_0102_metadata(record),
        "creatures": extract_0102_creatures(record),
    }


@_register_opcode(0x0220, "snapshot_handle")
def _handle_0220(record, inner) -> Dict[str, Any]:
    return {"handle": extract_0220_handle(record)}


# Standard "detail" handlers — auto-generated
for _opc, _kind, _ext in [
    (0x130B, "client_skill_select", extract_130b_skill_select),
    (0x1305, "battle_load_finish_req", extract_1305_load_finish_req),
    (0x1306, "battle_load_finish_rsp", extract_1306_load_finish_rsp),
    (0x1309, "supply_pet_req", extract_1309_supply_pet_req),
    (0x130A, "supply_pet_rsp", extract_130a_supply_pet_rsp),
    (0x1322, "server_skill_declare", extract_1322_skill_declare),
    (0x1324, "action_resolve", extract_1324_action),
    (0x13F4, "special_refresh", extract_13f4_refresh),
    (0x130C, "server_action_ack", extract_130c_result),
    (0x01A9, "client_action", extract_01a9_action),
    (0x1316, "battle_enter", extract_1316_enter),
    (0x131A, "round_start", extract_131a_round_start),
    (0x132C, "battle_finish", extract_132c_finish),
    (0x13FC, "pvp_perform", extract_13fc_pvp_perform),
    (0x13F3, "preplay", extract_13f3_preplay),
    (0x1312, "round_flow", extract_1312_round_flow),
    (0x1326, "auto_cmd", extract_1326_auto_cmd),
    (0x132E, "player_runaway_req", extract_132e_player_runaway_req),
    (0x132F, "player_runaway_rsp", extract_132f_player_runaway_rsp),
    (0x132A, "role_leave", extract_132a_role_leave),
    (0x132D, "force_finish", extract_132d_force_finish),
    (0x1334, "emoji", extract_1334_emoji),
    (0x133C, "catch_rsp", extract_133c_catch_rsp),
    (0x13F6, "ai_skill", extract_13f6_ai_skill),
    (0x1335, "round_op_query_req", extract_1335_round_op_query_req),
    (0x1336, "round_op_query_rsp", extract_1336_round_op_query_rsp),
    (0x13F9, "pk_again", extract_13f9_pk_again),
]:
    _OPCODE_REGISTRY[_opc] = (_kind, _make_detail_handler(_ext))


@_register_opcode(0x1313, "round_confirm")
def _handle_1313(record, inner) -> Dict[str, Any]:
    return {"detail": extract_1313_round_confirm(record)}


@_register_opcode(0x1314, "round_confirm_rsp")
def _handle_1314(record, inner) -> Dict[str, Any]:
    return {"detail": extract_1314_round_confirm_rsp(record)}


# ---------------------------------------------------------------------------
# Inner-message handlers
# ---------------------------------------------------------------------------


@_register_inner(390, "inner390_pair")
def _handle_inner390(record, inner) -> Dict[str, Any]:
    return {"detail": parse_inner390_detail(inner["fields"])}


@_register_inner(200, "inner200_commit")
def _handle_inner200(record, inner) -> Dict[str, Any]:
    return {"detail": parse_inner200_detail(inner["fields"])}


@_register_inner(51, "inner51_event")
def _handle_inner51(record, inner) -> Dict[str, Any]:
    return {"detail": parse_inner51_detail(inner["fields"])}


@_register_inner(1, "inner1_effect")
def _handle_inner1(record, inner) -> Dict[str, Any]:
    return {"detail": parse_inner1_detail(inner["fields"])}


# ---------------------------------------------------------------------------
# Public dispatch helper
# ---------------------------------------------------------------------------


def summarize(record: Any, inner: Optional[Any] = None) -> Tuple[str, Dict[str, Any]]:
    """Look up the appropriate handler and return ``(kind, result_dict)``.

    When *opcode* is ``0x0414`` and an *inner* payload is present the
    ``message_id`` inside *inner* is used to dispatch via
    ``_INNER_REGISTRY``.  Every other opcode is dispatched through
    ``_OPCODE_REGISTRY``.  Unknown opcodes fall back to
    ``("unknown", {"opcode": opcode})``.

    分发逻辑:
    1. opcode 0x0414 (通用容器) → 用 inner.message_id 查 _INNER_REGISTRY
    2. 其他 opcode → 直接查 _OPCODE_REGISTRY
    3. 都没命中 → 查 opcode_pb_map.json 获取消息名称
    4. 最终兜底 → "unknown"
    """
    return summarize_record(
        record,
        inner,
        opcode_registry=_OPCODE_REGISTRY,
        inner_registry=_INNER_REGISTRY,
    )
