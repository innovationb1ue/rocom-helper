"""BattlePerformInfo dispatcher tests."""
from __future__ import annotations

from src.protocol.battle_parts import perform_dispatch
from src.protocol.battle_parts.perform_dispatch import (
    _extract_1324_entry,
    _extract_perform_cmd,
)


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def test_extract_entry_attaches_meta_and_dispatches_skill_cast():
    entry = {
        "fields": [
            _v(1, 1),
            _v(2, 7),
            _v(11, 1),
            _v(14, 3),
            _v(26, 4),
            _v(27, 1),
            _v(39, 9),
            _sub(3, [_v(1, 1), _v(2, 2), _v(3, 712009000)]),
        ],
    }

    out = _extract_1324_entry(entry)

    assert out["kind"] == "skill_cast"
    assert out["type"] == 1
    assert out["group_id"] == 7
    assert out["is_group_head"] is True
    assert out["cast_moment"] == 3
    assert out["group_ref"] == 4
    assert out["is_last_hit"] is True
    assert out["exec_index"] == 9
    assert out["skill_id"] == 7120090


def test_extract_perform_cmd_summarizes_entries(monkeypatch):
    monkeypatch.setattr(perform_dispatch, "buff_name", lambda buff_id: f"Buff {buff_id}")
    skill_entry = {
        "fields": [
            _v(1, 1),
            _sub(3, [_v(1, 1), _v(2, 2), _v(3, 712009000)]),
        ],
    }
    effect_entry = {
        "fields": [
            _v(1, 2),
            _sub(4, [_v(1, 1), _v(2, 2), _v(3, 1001), _v(4, 1)]),
        ],
    }
    defeat_entry = {
        "fields": [
            _v(1, 7),
            _sub(9, [_v(1, 1), _v(2, 2), _v(3, 0)]),
        ],
    }
    container = {
        "fields": [
            _v(1, 10),
            _v(3, 20),
            _v(5, 30),
            _sub(2, skill_entry["fields"]),
            _sub(2, effect_entry["fields"]),
            _sub(2, defeat_entry["fields"]),
        ],
    }

    out = _extract_perform_cmd(container, {"opcode": 0x1324, "opcode_hex": "0x1324"})

    assert out["packet_state"] == 10
    assert out["packet_phase"] == 20
    assert out["packet_index"] == 30
    assert [entry["kind"] for entry in out["entries"]] == ["skill_cast", "effect_apply", "defeat"]
    assert out["primary_skill"]["skill_id"] == 7120090
    assert out["energy_event"]["kind"] == "skill_cast"
    assert out["effect_ids"] == [1001]
    assert out["effect_names"] == ["Buff 1001"]
    assert out["has_defeat"] is True
    assert out["opcode"] == 0x1324
    assert out["opcode_hex"] == "0x1324"
