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

import logging
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    first_sub,
    first_text,
    normalize_skill_id,
    pick_first,
    side_name,
    skill_name,
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
)

# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

_OPCODE_REGISTRY: Dict[int, Tuple[str, Callable]] = {}
_INNER_REGISTRY: Dict[int, Tuple[str, Callable]] = {}


def _make_detail_handler(extractor: Callable) -> Callable:
    """生成标准 handler: record → {"detail": extractor(record)}"""
    def _handler(record, inner):
        return {"detail": extractor(record)}
    return _handler


def _register_opcode(opcode: int, kind: str) -> Callable:
    """Decorator that registers *func* in ``_OPCODE_REGISTRY`` under *opcode*."""

    def _decorator(func: Callable) -> Callable:
        _OPCODE_REGISTRY[opcode] = (kind, func)
        return func

    return _decorator


def _register_inner(message_id: int, kind: str) -> Callable:
    """Decorator that registers *func* in ``_INNER_REGISTRY`` under *message_id*."""

    def _decorator(func: Callable) -> Callable:
        _INNER_REGISTRY[message_id] = (kind, func)
        return func

    return _decorator


# ---------------------------------------------------------------------------
# Inner-message detail parsers
# ---------------------------------------------------------------------------
# 内嵌消息解析器 — 处理 opcode 0x0414 中的内嵌消息。
# message_id 390 = 配对上下文 (pair_ctx, friendly/enemy 数据)
# message_id 200 = 提交确认 (commit flag, event_time)
# message_id 51 = 事件 (token, kind, values)
# message_id 1 = 效果 (header + effect details)


def _parse_inner390_detail(fields) -> Dict[str, Any]:
    fg = field_groups(fields)
    pe = next((e for e in fg.get(2, []) if e.get("sub")), None)
    detail: Dict[str, Any] = {"pair_ctx": pick_first(collect_varints(fields, 1))}
    if pe is None:
        return detail
    pg = field_groups(pe["sub"])
    for side, fn in (("friendly", 3), ("enemy", 4)):
        entries = pg.get(fn, [])
        if entries and entries[0].get("sub"):
            s = entries[0]["sub"]
            pid = pick_first(collect_varints(s, 2))
            base: Dict[str, Any] = {"pet_id": pid, "side_flag": pick_first(collect_varints(s, 10))}
            for i in range(3, 7):
                base[f"arg{i}"] = pick_first(collect_varints(s, i))
            if side == "enemy":
                base["arg1"] = pick_first(collect_varints(s, 1))
            detail[side] = base
    return detail


def _parse_inner200_detail(fields) -> Dict[str, Any]:
    fg = field_groups(fields)
    ce = next((e for e in fg.get(2, []) if e.get("sub")), None)
    detail: Dict[str, Any] = {"pair_ctx": pick_first(collect_varints(fields, 1))}
    if ce:
        c = ce["sub"]
        detail["commit"] = {
            "flag": pick_first(collect_varints(c, 1)),
            "arg2_ms_like": pick_first(collect_varints(c, 2)),
            "event_time_ms": pick_first(collect_varints(c, 3)),
            "code": pick_first(collect_varints(c, 4)),
        }
    return detail


def _parse_inner51_detail(fields) -> Dict[str, Any]:
    fg = field_groups(fields)
    pe = next((e for e in fg.get(2, []) if e.get("sub")), None)
    p = pe["sub"] if pe else None
    return {
        "token": pick_first(collect_varints(fields, 1)),
        "kind": pick_first(collect_varints(p, 1)) if p else None,
        "value2": pick_first(collect_varints(p, 2)) if p else None,
        "value3": pick_first(collect_varints(p, 3)) if p else None,
    }


def _parse_inner1_detail(fields) -> Dict[str, Any]:
    fg = field_groups(fields)
    pe = next((e for e in fg.get(11, []) if e.get("sub")), None)
    if pe is None:
        return {}
    pg = field_groups(pe["sub"])
    he = next((e for e in pg.get(1, []) if e.get("sub")), None)
    ee = next((e for e in pg.get(3, []) if e.get("sub")), None)
    detail: Dict[str, Any] = {}
    if he:
        hs = he["sub"]
        detail["header"] = {
            "kind": pick_first(collect_varints(hs, 1)),
            "actor_token": pick_first(collect_varints(hs, 2)),
            "actor_aux": pick_first(collect_varints(hs, 3)),
            "actor_ref": pick_first(collect_varints(hs, 5)),
            "target_ctx": pick_first(collect_varints(hs, 6)),
            "arg10": pick_first(collect_varints(hs, 10)),
            "arg11": pick_first(collect_varints(hs, 11)),
        }
    if ee:
        es = ee["sub"]
        detail["effect"] = {
            "effect_id": pick_first(collect_varints(es, 1)),
            "code": pick_first(collect_varints(es, 4)),
            "arg10": pick_first(collect_varints(es, 10)),
            "amount": pick_first(collect_varints(es, 11)),
            "arg12": pick_first(collect_varints(es, 12)),
            "arg13": pick_first(collect_varints(es, 13)),
            "arg15": pick_first(collect_varints(es, 15)),
            "arg16": pick_first(collect_varints(es, 16)),
            "arg27": pick_first(collect_varints(es, 27)),
            "arg32": pick_first(collect_varints(es, 32)),
        }
    return detail


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
    (0x132A, "role_leave", extract_132a_role_leave),
    (0x132D, "force_finish", extract_132d_force_finish),
    (0x1334, "emoji", extract_1334_emoji),
    (0x133C, "catch_rsp", extract_133c_catch_rsp),
    (0x13F6, "ai_skill", extract_13f6_ai_skill),
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
    return {"detail": _parse_inner390_detail(inner["fields"])}


@_register_inner(200, "inner200_commit")
def _handle_inner200(record, inner) -> Dict[str, Any]:
    return {"detail": _parse_inner200_detail(inner["fields"])}


@_register_inner(51, "inner51_event")
def _handle_inner51(record, inner) -> Dict[str, Any]:
    return {"detail": _parse_inner51_detail(inner["fields"])}


@_register_inner(1, "inner1_effect")
def _handle_inner1(record, inner) -> Dict[str, Any]:
    return {"detail": _parse_inner1_detail(inner["fields"])}


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
    opcode: int = record  # Assume record exposes the opcode directly
    if hasattr(record, "opcode"):
        opcode = record.opcode
    elif isinstance(record, dict):
        opcode = record.get("opcode", record)

    if opcode == 0x0414 and inner is not None:
        message_id: int = inner.get("message_id", -1) if isinstance(inner, dict) else getattr(inner, "message_id", -1)
        entry = _INNER_REGISTRY.get(message_id)
        if entry is not None:
            kind, handler = entry
            return kind, handler(record, inner)

    entry = _OPCODE_REGISTRY.get(opcode)
    if entry is not None:
        kind, handler = entry
        return kind, handler(record, inner)

    from src.data.loader import get_opcode_pb_meta
    meta = get_opcode_pb_meta(opcode)
    if meta is not None:
        msg = meta.get("message", "")
        return msg if msg else "unknown", {
            "opcode": opcode,
            "pb_type": meta.get("type", ""),
        }

    logger.warning("unknown opcode 0x%04X", opcode)
    return "unknown", {"opcode": opcode}
