"""effect perform entry handler 的直接单元测试。"""
from __future__ import annotations

from src.protocol.battle_parts.perform_entries_effects import (
    apply_buff_trigger_entry,
    apply_effect_apply_entry,
    apply_effect_link_entry,
    apply_effect_trigger_entry,
)
from src.protocol.proto_core import field_groups


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def test_effect_apply_extracts_buff_and_related_skills():
    entry = {
        "fields": [
            _sub(4, [_v(1, 1), _v(2, 2), _v(3, 1001), _v(4, 3)]),
            _sub(12, [
                _sub(3, [
                    _v(1, 1),
                    _v(2, 712009000),
                    _v(3, 11),
                    _v(4, 22),
                ]),
            ]),
        ]
    }
    out = {}

    apply_effect_apply_entry(out, field_groups(entry))

    assert out["kind"] == "effect_apply"
    assert out["actor_side"] == 1
    assert out["target_side"] == 2
    assert out["effect_id"] == 1001
    assert out["effect_stage"] == 3
    assert out["related_skills"][0]["owner_side"] == 1
    assert out["related_skills"][0]["skill_id"] == 7120090
    assert out["related_skills"][0]["arg3"] == 11
    assert out["related_skills"][0]["arg4"] == 22


def test_buff_trigger_extracts_alias_and_base_ids():
    entry = {
        "fields": [
            _sub(5, [
                _v(1, 1),
                _v(2, 2),
                _v(3, 2001),
                _v(6, 3001),
                _v(6, 3002),
                _v(7, 9),
                _v(8, 1),
                _v(9, 0),
            ]),
        ]
    }
    out = {}

    apply_buff_trigger_entry(out, field_groups(entry))

    assert out["kind"] == "buff_trigger"
    assert out["legacy_kind"] == "effect_stage"
    assert out["aliases"] == ["effect_stage"]
    assert out["actor_side"] == 1
    assert out["target_side"] == 2
    assert out["effect_id"] == 2001
    assert out["buff_id"] == 2001
    assert out["buffbase_ids"] == [3001, 3002]
    assert out["effect_base"] == 3001
    assert out["perform_type"] == 9
    assert out["need_select_pet"] is True
    assert out["frozen_death"] is False


def test_effect_link_extracts_buff_reference():
    entry = {"fields": [_sub(15, [_v(1, 1), _v(2, 2), _v(3, 1001)])]}
    out = {}

    apply_effect_link_entry(out, field_groups(entry))

    assert out["kind"] == "effect_link"
    assert out["actor_side"] == 1
    assert out["target_side"] == 2
    assert out["effect_id"] == 1001


def test_effect_trigger_extracts_result_and_params():
    entry = {
        "fields": [
            _sub(13, [
                _v(1, 1),
                _v(2, 2),
                _v(3, 1001),
                _v(5, 7),
                _v(6, 11),
                _v(6, 22),
            ]),
        ]
    }
    out = {}

    apply_effect_trigger_entry(out, field_groups(entry))

    assert out["kind"] == "effect_trigger"
    assert out["actor_side"] == 1
    assert out["target_side"] == 2
    assert out["effect_id"] == 1001
    assert out["trigger_result"] == 7
    assert out["trigger_params"] == [11, 22]
