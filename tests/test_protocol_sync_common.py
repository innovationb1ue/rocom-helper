"""battle sync 底层字段读取器的单元测试。"""
from __future__ import annotations

import struct

from src.protocol.battle_parts.sync_common import (
    _extract_buffdata_93_skill,
    _pick_fixed32_float,
    _pick_sync_value,
)


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _f32(field: int, value: float) -> dict:
    return {"field": field, "wire": 5, "raw_hex": struct.pack("<f", value).hex()}


def test_pick_sync_value_preserves_unsigned_and_decodes_signed_64bit():
    msg = {"fields": [_v(1, 42), _v(2, (1 << 64) - 7)]}

    assert _pick_sync_value(msg, 1) == 42
    assert _pick_sync_value(msg, 2, signed=True) == -7
    assert _pick_sync_value(msg, 99) is None


def test_pick_fixed32_float_ignores_invalid_wire_payloads():
    msg = {
        "fields": [
            {"field": 1, "wire": 5, "raw_hex": "zz"},
            _f32(1, 1.25),
        ]
    }

    assert _pick_fixed32_float(msg, 1) == 1.25


def test_extract_buffdata_93_skill_compacts_missing_values():
    msg = {
        "fields": [
            _v(1, (1 << 64) - 3),
            _v(2, 120),
            _v(3, (1 << 64) - 1),
            _v(4, 90001),
        ]
    }

    assert _extract_buffdata_93_skill(msg) == {
        "buffbase_id": -3,
        "value": 120,
        "side": -1,
        "role_uin": 90001,
    }
