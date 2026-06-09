"""场地/系统 perform entry handler 的直接单元测试。"""
from __future__ import annotations

from src.protocol.battle_parts.perform_entries_field import (
    apply_ai_action_entry,
    apply_data_update_entry,
    apply_idle_entry,
    apply_notify_perform_entry,
    apply_pvp_perform_marker_entry,
    apply_skill_state_entry,
    apply_weather_change_entry,
)
from src.protocol.proto_core import field_groups


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _t(field: int, value: str) -> dict:
    return {"field": field, "wire": 2, "text": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def test_idle_extracts_pet_id():
    entry = {"fields": [_sub(20, [_v(1, 1001)])]}
    out = {}

    apply_idle_entry(out, field_groups(entry))

    assert out == {"kind": "idle", "idle_pet_id": 1001}


def test_skill_state_extracts_caster_and_state_code():
    entry = {"fields": [_sub(24, [_v(1, 1001), _v(2, 9)])]}
    out = {}

    apply_skill_state_entry(out, field_groups(entry))

    assert out == {"kind": "skill_state", "caster_pet_id": 1001, "state_code": 9}


def test_weather_change_extracts_skill_weather_and_expire_round():
    entry = {"fields": [_sub(29, [_v(1, 7020370), _v(2, 999999), _v(5, 12)])]}
    out = {}

    apply_weather_change_entry(out, field_groups(entry))

    assert out["kind"] == "weather_change"
    assert out["skill_id"] == 7020370
    assert out["weather_id"] == 999999
    assert out["weather_name"] is None
    assert out["expire_round"] == 12


def test_notify_perform_extracts_tips_and_params():
    entry = {
        "fields": [
            _sub(30, [
                _v(1, 7),
                _v(2, 11),
                _v(2, 22),
                _t(3, "tip_id"),
                _t(4, "参数一"),
                _t(4, "参数二"),
                _v(5, 12345),
            ]),
        ]
    }
    out = {}

    apply_notify_perform_entry(out, field_groups(entry))

    assert out["kind"] == "notify_perform"
    assert out["notify_type"] == 7
    assert out["notify_data"] == [11, 22]
    assert out["tips_id"] == "tip_id"
    assert out["params"] == ["参数一", "参数二"]
    assert out["uin"] == 12345


def test_ai_action_and_pvp_marker_extract_simple_fields():
    ai_out = {}
    apply_ai_action_entry(ai_out, field_groups({"fields": [_sub(33, [
        _v(1, 1001), _v(2, 12345), _v(3, 2), _v(4, 9),
    ])]}))
    assert ai_out == {
        "kind": "ai_action",
        "pet_id": 1001,
        "uin": 12345,
        "ai_type": 2,
        "param": 9,
    }

    marker_out = {}
    apply_pvp_perform_marker_entry(marker_out, field_groups({"fields": [_sub(43, [
        _v(1, 12345), _v(2, 3),
    ])]}))
    assert marker_out == {"kind": "pvp_perform_marker", "uin": 12345, "pvp_type": 3}


def test_data_update_extracts_pet_id_and_skill_updates():
    entry = {
        "fields": [
            _sub(44, [
                _v(1, 12345),
                _sub(3, [_v(1, 100)]),
                _sub(7, [
                    _v(1, 100),
                    _sub(2, [
                        _v(39, 702037000),
                        _v(25, 1),
                        _v(9, 4),
                    ]),
                ]),
            ]),
        ]
    }
    out = {}

    apply_data_update_entry(out, field_groups(entry))

    assert out["kind"] == "data_update"
    assert out["uin"] == 12345
    assert out["pet_id"] == 100
    assert out["pet_skill_updates"][0]["pet_id"] == 100
    assert out["pet_skill_updates"][0]["skills"][0]["skill_id"] == 7020370
