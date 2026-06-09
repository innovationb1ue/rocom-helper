"""宠物生命周期 perform entry handler 的直接单元测试。"""
from __future__ import annotations

from src.protocol.battle_parts.perform_entries_pet import (
    apply_change_model_entry,
    apply_change_pet_entry,
    apply_defeat_entry,
    apply_revive_entry,
    apply_supply_pet_entry,
)
from src.protocol.proto_core import field_groups


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _t(field: int, value: str) -> dict:
    return {"field": field, "wire": 2, "text": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def test_defeat_extracts_actor_target_and_arg():
    entry = {"fields": [_sub(9, [_v(1, 1), _v(2, 401), _v(3, 7)])]}
    out = {}

    apply_defeat_entry(out, field_groups(entry))

    assert out["kind"] == "defeat"
    assert out["actor_side"] == 1
    assert out["target_side"] == 401
    assert out["defeat_arg"] == 7


def test_revive_extracts_actor_target():
    entry = {"fields": [_sub(10, [_v(1, 401), _v(2, 401)])]}
    out = {}

    apply_revive_entry(out, field_groups(entry))

    assert out["kind"] == "revive"
    assert out["actor_side"] == 401
    assert out["target_side"] == 401


def test_change_pet_extracts_new_pet_runtime_fields():
    battle_attr = [0, 300, 11, 22, 33, 44, 55] + [0] * 18 + [250]
    entry = {
        "fields": [
            _sub(18, [
                _v(1, 1),
                _v(2, 1001),
                _v(3, 1002),
                _sub(4, [
                    _sub(1, [_v(6, value) for value in battle_attr] + [_v(64, 9001)]),
                    _sub(2, [
                        _v(2, 1002),
                        _t(3, "测试宠"),
                        _v(6, 1),
                        _v(6, 2),
                        _v(10, 50),
                        _v(15, 2002),
                        _v(33, 8),
                    ]),
                ]),
                _v(5, 1),
            ]),
        ]
    }
    out = {}

    apply_change_pet_entry(out, field_groups(entry))

    assert out["kind"] == "change_pet"
    assert out["rest_pet_id"] == 1001
    assert out["battle_pet_id"] == 1002
    assert out["is_cmd"] == 1
    assert out["new_pet_id"] == 1002
    assert out["new_pet_name"] == "测试宠"
    assert out["new_pet_types"] == [1, 0]
    assert out["new_pet_level"] == 50
    assert out["new_pet_base_conf_id"] == 2002
    assert out["new_pet_battle_stats"] == [300, 11, 22, 33, 44, 55]
    assert out["new_pet_current_hp"] == 250
    assert out["new_pet_max_hp"] == 300
    assert out["new_pet_energy"] == 8
    assert out["new_pet_passive_skill_id"] == 9001


def test_change_model_extracts_model_and_original_pet_fields():
    battle_attr = [0, 280, 10, 20, 30, 40, 50] + [0] * 18 + [123]
    entry = {
        "fields": [
            _sub(32, [
                _v(1, 401),
                _v(2, 3001),
                _sub(3, [
                    _sub(1, [_v(6, value) for value in battle_attr] + [
                        _v(21, 4002),
                        _v(22, 3002),
                        _t(23, "模型宠"),
                    ]),
                    _sub(2, [
                        _v(2, 4001),
                        _t(3, "原始宠"),
                        _v(6, 1),
                        _v(10, 60),
                        _v(15, 3001),
                    ]),
                ]),
                _v(4, 9),
            ]),
        ]
    }
    out = {}

    apply_change_model_entry(out, field_groups(entry))

    assert out["kind"] == "change_model"
    assert out["pet_id"] == 401
    assert out["old_base_id"] == 3001
    assert out["role_magic_flag"] == 9
    assert out["model_pet_id"] == 4002
    assert out["model_base_id"] == 3002
    assert out["model_pet_name"] == "模型宠"
    assert out["model_battle_stats"] == [280, 10, 20, 30, 40, 50]
    assert out["model_current_hp"] == 123
    assert out["model_max_hp"] == 280
    assert out["original_pet_id"] == 4001
    assert out["original_pet_name"] == "原始宠"
    assert out["original_pet_types"] == [1]
    assert out["original_pet_level"] == 60
    assert out["original_base_conf_id"] == 3001


def test_supply_pet_extracts_player_and_pet_positions():
    entry = {
        "fields": [
            _sub(45, [
                _v(1, 123),
                _sub(2, [_v(1, 1001), _v(2, 3)]),
                _sub(2, [_v(1, 1002), _v(2, 4)]),
            ]),
        ]
    }
    out = {}

    apply_supply_pet_entry(out, field_groups(entry))

    assert out["kind"] == "supply_pet"
    assert out["player_id"] == 123
    assert out["supply_pets"] == [
        {"pet_id": 1001, "pet_pos": 3},
        {"pet_id": 1002, "pet_pos": 4},
    ]
