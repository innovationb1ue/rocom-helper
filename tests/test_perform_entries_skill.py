"""技能相关 perform entry handler 的直接单元测试。"""
from __future__ import annotations

from src.protocol.battle_parts.perform_entries_skill import (
    apply_combo_skill_cast_entry,
    apply_role_skill_cast_entry,
    apply_skill_pos_change_entry,
    apply_special_move_entry,
)
from src.protocol.proto_core import field_groups


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def test_role_skill_cast_extracts_role_skill_fields():
    entry = {"fields": [_sub(37, [_v(1, 12345), _v(2, 702037000), _v(3, 1001), _v(4, 1)])]}
    out = {}

    apply_role_skill_cast_entry(out, field_groups(entry))

    assert out["kind"] == "role_skill_cast"
    assert out["caster_uin"] == 12345
    assert out["skill_id"] == 7020370
    assert out["pet_id"] == 1001
    assert out["is_call_success"] is True


def test_combo_skill_cast_extracts_actor_target_and_combo_fields():
    entry = {"fields": [_sub(38, [
        _v(1, 1001),
        _v(2, 401),
        _v(2, 402),
        _v(3, 702037000),
        _v(8, 2),
        _v(9, 3),
    ])]}
    out = {}

    apply_combo_skill_cast_entry(out, field_groups(entry))

    assert out["kind"] == "combo_skill_cast"
    assert out["actor_side"] == 1001
    assert out["target_side"] == 401
    assert out["caster_id"] == 1001
    assert out["target_id"] == [401, 402]
    assert out["skill_id_x100"] == 702037000
    assert out["skill_id"] == 7020370
    assert out["combo_index"] == 2
    assert out["combo_count"] == 3


def test_skill_pos_change_extracts_position_infos():
    entry = {"fields": [_sub(46, [
        _v(1, 1001),
        _sub(2, [_v(1, 7020370), _v(2, 1), _v(3, 2), _v(4, 9)]),
        _sub(2, [_v(1, 7110200), _v(2, 3), _v(3, 4), _v(4, 8)]),
    ])]}
    out = {}

    apply_skill_pos_change_entry(out, field_groups(entry))

    assert out["kind"] == "skill_pos_change"
    assert out["pet_id"] == 1001
    assert out["skill_pos_infos"] == [
        {"skill_id": 7020370, "old_pos": 1, "new_pos": 2, "change_type": 9, "skill_name": out["skill_pos_infos"][0]["skill_name"]},
        {"skill_id": 7110200, "old_pos": 3, "new_pos": 4, "change_type": 8, "skill_name": "超导"},
    ]


def test_special_move_extracts_skill_reference():
    entry = {"fields": [_sub(47, [
        _v(1, 1001),
        _v(2, 33),
        _v(3, 2),
        _v(4, 7),
        _v(5, 702037000),
    ])]}
    out = {}

    apply_special_move_entry(out, field_groups(entry))

    assert out["kind"] == "special_move"
    assert out["pet_id"] == 1001
    assert out["special_move_id"] == 33
    assert out["special_move_type"] == 2
    assert out["round"] == 7
    assert out["skill_id"] == 7020370
