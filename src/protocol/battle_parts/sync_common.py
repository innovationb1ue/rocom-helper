"""Low-level readers shared by battle sync-data extractors."""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Optional

from src.protocol.proto_core import collect_varints, field_groups, maybe_signed64, pick_first
from src.protocol.battle_schema import _compact_dict


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


def _extract_simple_subitems(msg: Dict[str, Any], field_no: int, spec: Dict[int, tuple]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(field_no, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item = _compact_dict({
            name: _pick_sync_value(sub, fn, signed)
            for fn, (name, signed) in spec.items()
        })
        if item:
            items.append(item)
    return items
