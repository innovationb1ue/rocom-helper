"""战斗 perform 同步字段解析测试。"""
from __future__ import annotations

import struct
from pathlib import Path

from src.protocol.battle import _extract_1324_entry
from src.protocol.opcodes import summarize
from tests.packet_reader import load_battle_packets


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def _f32(field: int, value: float) -> dict:
    return {"field": field, "wire": 5, "raw_hex": struct.pack("<f", value).hex()}


def test_extract_perform_meta_and_sync_data_signed_values():
    """解析 group 元信息、pet_sync、skill_sync，并把负 delta 转回有符号数。"""
    entry = {
        "fields": [
            _v(1, 2),
            _v(2, 7),
            _v(11, 1),
            _sub(12, [
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
            ]),
            _v(14, 11),
            _v(26, 3),
            _v(39, 5),
            _sub(4, [_v(1, 1), _v(2, 401), _v(3, 1001), _v(4, 1)]),
        ]
    }

    out = _extract_1324_entry(entry)

    assert out["kind"] == "effect_apply"
    assert out["group_id"] == 7
    assert out["is_group_head"] is True
    assert out["cast_moment"] == 11
    assert out["group_ref"] == 3
    assert out["exec_index"] == 5
    pet_sync = out["sync_data"]["pet_sync"][0]
    assert pet_sync["hp_change"] == -20
    assert pet_sync["hp_result"] == 280
    assert pet_sync["energy_change"] == -1
    assert pet_sync["energy_result"] == 9
    skill_sync = out["sync_data"]["skill_sync"][0]
    assert skill_sync["skill_id"] == 7020370
    assert skill_sync["damage_param_change"] == -5
    assert skill_sync["damage_param_result"] == 150
    assert skill_sync["cost_energy_change"] == -1
    assert skill_sync["cost_energy_result"] == 4
    assert skill_sync["hp_per_energy"] == 1.25
    assert skill_sync["state"] == 3
    assert skill_sync["damage_type"] == 2
    changed = out["sync_data"]["skill_change_sync"][0]
    assert changed["skill_id"] == 7020370
    assert changed["skill_data"]["state"] == 1
    assert changed["skill_data"]["type"] == 1
    assert changed["skill_data"]["cost_energy"] == 4
    assert changed["skill_data"]["raw_cost_energy"] == 4
    assert changed["skill_data"]["damage_params"][0] == {"pet_id": 401, "damage_param": 150}
    assert changed["skill_data"]["restraint_types"][0] == {"pet_id": 401, "restraint_type": -1}
    assert changed["skill_data"]["cd_round"] == 2
    assert changed["skill_data"]["damage_type"] == 2
    item_sync = out["sync_data"]["item_sync"][0]
    assert item_sync["item_id"] == 9001
    assert item_sync["battle_use_time_remain"] == 1


def test_extract_data_update_pet_skill_updates():
    """解析 data_update.pet_skill 中的技能运行时字段。"""
    entry = {
        "fields": [
            _v(1, 35),
            _v(2, 9),
            _v(14, 0),
            _v(39, 2),
            _sub(44, [
                _v(1, 12345),
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
                ]),
            ]),
        ]
    }

    out = _extract_1324_entry(entry)

    assert out["kind"] == "data_update"
    assert out["uin"] == 12345
    update = out["pet_skill_updates"][0]
    assert update["pet_id"] == 100
    assert update["skills"][0]["skill_id"] == 7020370
    assert update["skills"][0]["equipped_slot"] == 1
    assert update["skills"][0]["cost_energy"] == 4
    assert update["skills"][0]["raw_cost_energy"] == 5
    assert update["skills"][0]["state"] == 2
    assert update["skills"][0]["type"] == 1
    assert update["skills"][0]["cd_round"] == 3
    assert update["skills"][0]["damage_type"] == 2
    assert update["skills"][0]["damage_params"][0] == {"pet_id": 401, "damage_param": 180}
    assert update["skills"][0]["restraint_types"][0] == {"pet_id": 401, "restraint_type": 1}


def test_real_fixture_pet_skill_round_field_numbers():
    """真实回放中 PetSkillRoundData 应按 field2/3/39 解析状态、类型和技能 ID。"""
    packets = load_battle_packets(Path("tests/fixtures/packets/battle_session_1"))
    for item in packets:
        if item["opcode"] != 0x1324:
            continue
        _, summary = summarize(item["record"], None)
        for entry in summary["detail"].get("entries", []):
            for update in entry.get("pet_skill_updates", []) or []:
                for skill in update.get("skills", []) or []:
                    if skill.get("skill_id") == 7120130:
                        assert skill["state"] == 1
                        assert skill["type"] == 1
                        assert skill["cost_energy"] == 7
                        assert skill["equipped_slot"] == 3
                        return
    raise AssertionError("battle_session_1 中应包含 7120130 的 PetSkillRoundData")
