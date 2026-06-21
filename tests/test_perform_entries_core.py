"""核心 perform entry handler 的直接单元测试。"""
from __future__ import annotations

from src.protocol.battle_parts.perform_entries_core import (
    apply_damage_entry,
    apply_energy_entry,
    apply_heal_entry,
    apply_skill_cast_entry,
)
from src.protocol.proto_core import field_groups


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def test_skill_cast_extracts_skill_and_energy_delta():
    entry = {
        "fields": [
            _sub(3, [_v(1, 1), _v(2, 2), _v(3, 712009000)]),
            _sub(12, [
                _sub(2, [
                    _v(25, (1 << 64) - 2),
                    _v(26, 8),
                ]),
            ]),
        ]
    }
    out = {}

    apply_skill_cast_entry(out, field_groups(entry))

    assert out["kind"] == "skill_cast"
    assert out["actor_side"] == 1
    assert out["target_side"] == 2
    assert out["skill_id"] == 7120090
    assert out["energy_delta"] == -2
    assert out["energy_after"] == 8


def test_damage_extracts_damage_and_hp_sync_hints():
    entry = {
        "fields": [
            _sub(6, [
                _v(1, 1),
                _v(2, 2),
                _v(3, 712009000),
                _v(5, 1),
                _v(7, (1 << 64) - 1),
                _v(9, 2),
            ]),
            _sub(12, [
                _sub(2, [
                    _v(1, 2),
                    _v(11, 88),
                    _v(12, (1 << 64) - 12),
                    _v(13, 76),
                ]),
                _sub(2, [
                    _v(1, 2),
                    _v(2, (1 << 64) - 76),
                    _v(3, 300),
                ]),
            ]),
        ]
    }
    out = {}

    apply_damage_entry(out, field_groups(entry))

    assert out["kind"] == "damage"
    assert out["skill_id"] == 7120090
    assert out["is_critical"] is True
    assert out["restraint_type"] == -1
    assert out["dam_type"] == 2
    assert out["original_damage"] == 88
    assert out["damage_change"] == -12
    assert out["damage_result"] == 76
    assert out["damage"] == 88
    assert out["damage_target_side"] == 2
    assert out["hp_change"] == -76
    assert out["hp_result"] == 300
    assert out["target_hp_after"] == 300


def test_heal_extracts_target_hp_after():
    entry = {
        "fields": [
            _sub(7, [_v(1, 1), _v(2, 1), _v(3, 1001), _v(4, 2)]),
            _sub(12, [_sub(2, [_v(1, 1), _v(3, 250)])]),
        ]
    }
    out = {}

    apply_heal_entry(out, field_groups(entry))

    assert out["kind"] == "heal"
    assert out["actor_side"] == 1
    assert out["target_side"] == 1
    assert out["source_id"] == 1001
    assert out["heal_type"] == 2
    assert out["target_hp_after"] == 250


def test_energy_extracts_delta_and_after():
    entry = {
        "fields": [
            _sub(8, [_v(1, 0), _v(2, 1), _v(3, 1001)]),
            _sub(12, [_sub(2, [_v(25, 3), _v(26, 10)])]),
        ]
    }
    out = {}

    apply_energy_entry(out, field_groups(entry))

    assert out["kind"] == "energy"
    assert out["actor_side"] == 0
    assert out["target_side"] == 1
    assert out["source_id"] == 1001
    assert out["energy_delta"] == 3
    assert out["energy_after"] == 10
