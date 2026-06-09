"""战斗 perform sync-data 解析器的直接单元测试。"""
from __future__ import annotations

import struct

from src.protocol.battle_parts.sync import _extract_pet_skill_updates, _extract_sync_data


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def _f32(field: int, value: float) -> dict:
    return {"field": field, "wire": 5, "raw_hex": struct.pack("<f", value).hex()}


def test_extract_sync_data_without_perform_entry_wrapper():
    sync = {
        "fields": [
            _sub(2, [
                _v(1, 1),
                _v(2, (1 << 64) - 20),
                _v(3, 280),
                _v(25, (1 << 64) - 1),
                _v(26, 9),
            ]),
            _sub(3, [
                _v(1, 1),
                _v(2, 702037000),
                _v(3, (1 << 64) - 5),
                _v(4, 150),
                _v(9, (1 << 64) - 1),
                _v(10, 4),
                _f32(15, 1.25),
                _v(17, 3),
                _v(18, 2),
            ]),
            _sub(5, [
                _v(1, 1),
                _v(2, 702037000),
                _sub(3, [
                    _v(2, 1),
                    _v(3, 1),
                    _v(9, 4),
                    _v(25, 1),
                    _sub(26, [_v(1, 401), _v(2, 150)]),
                    _sub(27, [_v(1, 401), _v(2, (1 << 64) - 1)]),
                    _v(28, 2),
                    _v(39, 702037000),
                    _v(52, 4),
                    _v(63, 2),
                ]),
            ]),
            _sub(7, [
                _v(1, 9001),
                _v(4, 3),
                _v(6, 1),
                _v(10, 2),
                _v(11, 3),
                _v(12, 1),
            ]),
        ]
    }

    out = _extract_sync_data(sync)

    assert out["pet_sync"][0]["hp_change"] == -20
    assert out["pet_sync"][0]["energy_change"] == -1
    assert out["skill_sync"][0]["skill_id"] == 7020370
    assert out["skill_sync"][0]["damage_param_change"] == -5
    assert out["skill_sync"][0]["hp_per_energy"] == 1.25
    changed = out["skill_change_sync"][0]
    assert changed["skill_id"] == 7020370
    assert changed["skill_data"]["damage_params"][0] == {"pet_id": 401, "damage_param": 150}
    assert changed["skill_data"]["restraint_types"][0] == {"pet_id": 401, "restraint_type": -1}
    assert out["item_sync"][0]["battle_use_time_remain"] == 1


def test_extract_pet_skill_updates_without_data_update_entry_wrapper():
    msg = {
        "fields": [
            _sub(7, [
                _v(1, 100),
                _sub(2, [
                    _v(39, 702037000),
                    _v(25, 1),
                    _v(9, 4),
                    _v(2, 2),
                    _v(3, 1),
                    _v(28, 3),
                    _sub(26, [_v(1, 401), _v(2, 180)]),
                    _sub(27, [_v(1, 401), _v(2, 1)]),
                    _v(52, 5),
                    _v(63, 2),
                ]),
                _sub(2, [
                    _v(39, 711020000),
                    _v(25, 6),
                    _v(9, 3),
                ]),
            ]),
        ]
    }

    updates = _extract_pet_skill_updates(msg)

    assert updates[0]["pet_id"] == 100
    assert updates[0]["skills"][0]["skill_id"] == 7020370
    assert updates[0]["skills"][0]["source"] == "data_update.pet_skill.skills"
    assert updates[0]["skills"][0]["source_index"] == 0
    assert updates[0]["skills"][0]["damage_type"] == 2
    assert updates[0]["skills"][0]["damage_params"][0] == {"pet_id": 401, "damage_param": 180}
    assert updates[0]["skills"][1]["skill_id"] == 7110200
    assert updates[0]["skills"][1]["source_index"] == 1
