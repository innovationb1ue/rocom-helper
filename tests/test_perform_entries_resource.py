"""资源类 perform entry handler 的直接单元测试。"""
from __future__ import annotations

from src.protocol.battle_parts.perform_entries_resource import (
    apply_sp_energy_change_entry,
    apply_sp_energy_trigger_entry,
)
from src.protocol.proto_core import field_groups


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def test_sp_energy_change_extracts_element_and_signed_values():
    entry = {
        "fields": [
            _sub(17, [
                _v(1, 2),
                _sub(2, [_v(1, 7), _v(2, 3)]),
                _v(3, 11),
                _v(4, 1001),
                _v(5, 401),
                _v(6, (1 << 64) - 5),
                _v(7, 8),
            ]),
        ]
    }
    out = {}

    apply_sp_energy_change_entry(out, field_groups(entry))

    assert out["kind"] == "sp_energy_change"
    assert out["sp_change_type"] == 2
    assert out["sp_element"] == {"dam_type": 7, "stack": 3}
    assert out["sp_change_src"] == 11
    assert out["caster_id"] == 1001
    assert out["target_id"] == 401
    assert out["change_value"] == -5
    assert out["real_change_value"] == 8


def test_sp_energy_trigger_extracts_old_and_new_skill_ids():
    entry = {
        "fields": [
            _sub(16, [
                _v(1, 4),
                _v(2, 2),
                _v(3, 1001),
                _v(4, 702037000),
                _v(5, 711020000),
            ]),
        ]
    }
    out = {}

    apply_sp_energy_trigger_entry(out, field_groups(entry))

    assert out["kind"] == "sp_energy_trigger"
    assert out["dam_type"] == 4
    assert out["trigger_type"] == 2
    assert out["caster_id"] == 1001
    assert out["old_skill_id"] == 7020370
    assert out["new_skill_id"] == 7110200
