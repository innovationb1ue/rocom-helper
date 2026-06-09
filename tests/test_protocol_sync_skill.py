"""PetSkillRoundData 技能运行时解析器的单元测试。"""
from __future__ import annotations

import struct

from src.protocol.battle_parts.sync_skill import _extract_pet_skill_round_data


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def _f32(field: int, value: float) -> dict:
    return {"field": field, "wire": 5, "raw_hex": struct.pack("<f", value).hex()}


def test_extract_pet_skill_round_data_keeps_skill_runtime_contract():
    msg = {
        "fields": [
            _v(1, 12345),
            _v(2, (1 << 64) - 2),
            _v(3, 1),
            _v(9, 4),
            _f32(7, 0.75),
            _v(25, 2),
            _sub(26, [_v(1, 401), _v(2, 180)]),
            _sub(27, [_v(1, 401), _v(2, (1 << 64) - 1)]),
            _sub(34, [_v(1, 9001), _v(2, (1 << 64) - 3)]),
            _sub(35, [_v(1, 9002), _v(2, (1 << 64) - 4), _v(5, 702037000)]),
            _sub(41, [_v(1, 401), _v(2, (1 << 64) - 8)]),
            _sub(45, [_f32(1, 1.5), _v(2, (1 << 64) - 6)]),
            _sub(48, [_v(1, (1 << 64) - 2), _v(2, 3)]),
            _sub(59, [_v(1, 7), _v(2, (1 << 64) - 1)]),
            _v(39, 702037000),
            _v(52, 4),
            _v(63, 2),
            _v(65, (1 << 64) - 10),
        ]
    }

    out = _extract_pet_skill_round_data(msg)

    assert out["raw_round_skill_id"] == 12345
    assert out["skill_id"] == 7020370
    assert out["state"] == -2
    assert out["type"] == 1
    assert out["cost_energy"] == 4
    assert out["hp_per_energy"] == 0.75
    assert out["equipped_slot"] == 2
    assert out["damage_type"] == 2
    assert out["damage_params"] == [{"pet_id": 401, "damage_param": 180}]
    assert out["restraint_types"] == [{"pet_id": 401, "restraint_type": -1}]
    assert out["cd_info"] == [{"buff_id": 9001, "value": -3}]
    assert out["enhance_info"][0]["skill_id"] == 7020370
    assert out["cr_damage_params"] == [{"pet_id": 401, "param": -8}]
    assert out["skill_buff"]["damage_param"] == -6
    assert out["trans_info"] == {"trans_time": -2, "initial_pos": 3}
    assert out["set_cost_info"] == [{"reason_id": 7, "cost": -1}]
    assert out["cost_energy_buff_factor_list"] == [-10]
