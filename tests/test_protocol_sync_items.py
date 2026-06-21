"""通用 BattleSyncData item 抽取测试。"""
from __future__ import annotations

import struct

from src.protocol.battle_parts.sync_items import (
    _PET_SYNC_FIELDS,
    _SKILL_SYNC_FIELDS,
    _extract_sync_items,
    _extract_task_infos,
)


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def _f32(field: int, value: float) -> dict:
    return {"field": field, "wire": 5, "raw_hex": struct.pack("<f", value).hex()}


def test_extract_pet_sync_items_decodes_signed_values_state_bits_and_triggered_buffs():
    sync = {
        "fields": [
            _sub(2, [
                _v(1, 401),
                _v(2, (1 << 64) - 20),
                _v(3, 280),
                _v(25, (1 << 64) - 1),
                _v(26, 9),
                _v(27, 11),
                _v(27, 12),
                _sub(37, [
                    _v(1, (1 << 64) - 3),
                    _v(2, 120),
                    _v(3, (1 << 64) - 1),
                    _v(4, 90001),
                ]),
            ]),
        ],
    }

    out = _extract_sync_items(sync, 2, _PET_SYNC_FIELDS)

    assert out == [
        {
            "pet_id": 401,
            "hp_change": -20,
            "hp_result": 280,
            "energy_change": -1,
            "energy_result": 9,
            "state_bit_results": [11, 12],
            "triggered_buffs": [
                {
                    "buffbase_id": -3,
                    "value": 120,
                    "side": -1,
                    "role_uin": 90001,
                },
            ],
        },
    ]


def test_extract_skill_sync_items_normalizes_skill_id_and_float():
    sync = {
        "fields": [
            _sub(3, [
                _v(1, 401),
                _v(2, 702037000),
                _v(3, (1 << 64) - 5),
                _v(4, 150),
                _f32(15, 1.25),
            ]),
        ],
    }

    out = _extract_sync_items(sync, 3, _SKILL_SYNC_FIELDS)

    assert out[0]["pet_id"] == 401
    assert out[0]["skill_id"] == 7020370
    assert out[0]["damage_param_change"] == -5
    assert out[0]["damage_param_result"] == 150
    assert out[0]["hp_per_energy"] == 1.25


def test_extract_task_infos_compacts_empty_values():
    sync = {
        "fields": [
            _sub(8, [_v(1, 1001), _v(2, (1 << 64) - 2), _v(3, 90001)]),
            _sub(8, []),
        ],
    }

    assert _extract_task_infos(sync) == [
        {"task_id": 1001, "task_state": -2, "uin": 90001},
    ]
