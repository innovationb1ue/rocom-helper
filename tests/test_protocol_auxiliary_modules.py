"""Battle auxiliary protocol extractor module tests."""
from __future__ import annotations

from src.protocol.battle_parts import auxiliary
from src.protocol.battle_parts import auxiliary_actions, auxiliary_creatures, auxiliary_simple


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _t(field: int, text: str) -> dict:
    return {"field": field, "wire": 2, "text": text}


def _raw(field: int, raw_hex: str) -> dict:
    return {"field": field, "wire": 2, "raw_hex": raw_hex}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def test_auxiliary_facade_reexports_focused_extractors():
    assert auxiliary.extract_0102_creatures is auxiliary_creatures.extract_0102_creatures
    assert auxiliary.extract_0102_metadata is auxiliary_creatures.extract_0102_metadata
    assert auxiliary.extract_0220_handle is auxiliary_actions.extract_0220_handle
    assert auxiliary.extract_01a9_action is auxiliary_actions.extract_01a9_action
    assert auxiliary.extract_1334_emoji is auxiliary_simple.extract_1334_emoji


def test_0102_metadata_extracts_player_and_pet_fields():
    record = {
        "root": {"fields": [
            _sub(1, [_v(1, 100), _v(2, 200), _t(3, "玩家")]),
            _sub(3, [_v(1, 11), _v(1, 22), _v(2, 11)]),
        ]},
    }

    out = auxiliary_creatures.extract_0102_metadata(record)

    assert out == {
        "user_id": 100,
        "uin": 200,
        "nickname": "玩家",
        "pet_ids": [11, 22],
        "active_pet_id": 11,
    }


def test_0102_creatures_decodes_raw_embedded_creature_list(monkeypatch):
    parsed_payloads = []

    def fake_parse(payload: bytes) -> dict:
        parsed_payloads.append(payload)
        return {"payload": payload}

    def fake_extract(parsed: dict, **_kwargs) -> dict:
        slot = parsed["payload"][0] + 1
        return {"slot": slot, "name": f"宠物{slot}"}

    monkeypatch.setattr(auxiliary_creatures, "parse_proto_message", fake_parse)
    monkeypatch.setattr(auxiliary_creatures, "extract_creature", fake_extract)
    record = {
        "root": {"fields": [
            _sub(2, [
                _raw(4, "0a01010a0100"),
            ]),
        ]},
    }

    out = auxiliary_creatures.extract_0102_creatures(record)

    assert parsed_payloads == [b"\x01", b"\x00"]
    assert out == [
        {"slot": 1, "name": "宠物1"},
        {"slot": 2, "name": "宠物2"},
    ]


def test_0220_handle_extracts_nested_and_direct_fallbacks():
    nested = {"root": {"fields": [_sub(2, [_v(1, 777)])]}}
    direct = {"root": {"fields": [_v(1, 888)]}}

    assert auxiliary_actions.extract_0220_handle(nested) == 777
    assert auxiliary_actions.extract_0220_handle(direct) == 888


def test_01a9_action_extracts_candidate_ids_and_actor_metadata():
    record = {
        "root": {"fields": [
            _sub(4, [
                _v(1, 555),
                _sub(2, [
                    _sub(1, [_v(1, 101), _v(2, 102)]),
                ]),
                _v(4, 9),
            ]),
        ]},
    }

    out = auxiliary_actions.extract_01a9_action(record)

    assert out == {
        "candidate_ids": [101, 102],
        "actor_token": 555,
        "raw_kind": 9,
        "primary_id": 101,
    }


def test_simple_auxiliary_schema_path_keeps_opcode_contract():
    out = auxiliary_simple.extract_1334_emoji({
        "opcode": 0x1334,
        "opcode_hex": "0x1334",
        "_message_name": "EmojiNotify",
        "_decoded": {"emoji_id": 1},
    })

    assert out == {
        "emoji_id": 1,
        "opcode": 0x1334,
        "opcode_hex": "0x1334",
    }
