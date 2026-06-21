"""Battle command protocol extractor module tests."""
from __future__ import annotations

from src.protocol.battle_parts import commands
from src.protocol.battle_parts import command_refresh, command_results, command_skills


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def test_command_facade_reexports_focused_extractors():
    assert commands.extract_130b_skill_select is command_skills.extract_130b_skill_select
    assert commands.extract_1322_skill_declare is command_skills.extract_1322_skill_declare
    assert commands.extract_130c_result is command_results.extract_130c_result
    assert commands.extract_13f4_refresh is command_refresh.extract_13f4_refresh


def test_skill_select_schema_path_keeps_command_contract(monkeypatch):
    monkeypatch.setattr(
        command_skills,
        "_schema_payload",
        lambda _record, _message: {
            "wl_req_id": 3,
            "req_type": 1,
            "req": [{
                "cast_skill": {
                    "caster_pet_id": 1,
                    "target_pet_id": 401,
                    "target_pet_pos": 0,
                    "skill_id": 712009000,
                },
                "change_pet": {"pet_id": 99},
                "use_item": {"item_id": 88},
            }],
        },
    )
    monkeypatch.setattr(command_skills, "_attach_skill_meta", lambda out, sid: out.update({"meta_skill_id": sid}))

    out = command_skills.extract_130b_skill_select({"opcode": 0x130B, "opcode_hex": "0x130b", "root": {"fields": []}})

    assert out["extract_kind"] == "skill_select"
    assert out["cmd_slot"] == 3
    assert out["cmd_flag"] == 1
    assert out["actor_side"] == 1
    assert out["target_side"] == 401
    assert out["skill_id_x100"] == 712009000
    assert out["skill_id"] == 7120090
    assert out["change_pet_id"] == 99
    assert out["item_id"] == 88
    assert out["meta_skill_id"] == 7120090
    assert out["schema_message"] == "ZoneBattleCmdPushbackReq"
    assert out["parse_quality"] == "schema_postprocess"


def test_skill_declare_raw_path_tags_extract_kind(monkeypatch):
    def fake_extract(record, extra_fields=None, **_kwargs):
        return {"skill_id": 1, **(extra_fields or {})}

    monkeypatch.setattr(command_skills, "_extract_skill_or_special", fake_extract)

    out = command_skills.extract_1322_skill_declare({
        "root": {"fields": [_v(1, 12345)]},
    })

    assert out == {"skill_id": 1, "battle_token": 12345, "extract_kind": "skill_declare"}


def test_result_infers_willpower_action_from_wrappers():
    wrappers = [{"dynamic_skills": [{"skill_id": command_results._WILLPOWER_SKILL_ID}]}]

    assert command_results.infer_action_from_wrappers(wrappers) == "愿力强化"
    assert command_results.infer_action_from_wrappers([{"dynamic_skills": [{"skill_id": 1}]}]) is None


def test_refresh_extracts_energy_bottle_and_sorts_skill_options(monkeypatch):
    monkeypatch.setattr(command_refresh, "skill_name", lambda sid: f"技能{sid}")
    record = {
        "opcode": 0x13F4,
        "opcode_hex": "0x13f4",
        "root": {"fields": [
            _sub(1, [
                _v(1, 10),
                _v(3, 20),
                _v(5, 30),
                _sub(2, [
                    _v(1, 14),
                    _sub(12, [
                        _sub(3, [_v(2, 712009000), _v(10, 2)]),
                        _sub(3, [_v(2, 706013000), _v(10, 1)]),
                    ]),
                    _sub(19, [_v(1, 123456), _v(2, 7)]),
                ]),
                _sub(2, [
                    _v(1, 6),
                    _sub(12, [_sub(2, [_v(25, 5), _v(26, 10)])]),
                ]),
            ]),
        ]},
    }

    out = command_refresh.extract_13f4_refresh(record)

    assert out["kind"] == "energy_bottle"
    assert out["action_name"] == "能量瓶"
    assert out["energy_delta"] == 5
    assert out["energy_after"] == 10
    assert out["battle_token"] == 123456
    assert [item["skill_id"] for item in out["skill_options"]] == [7060130, 7120090]
