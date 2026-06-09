"""Generic perform fallback extraction tests."""
from __future__ import annotations

from src.protocol.battle_parts.perform_generic import apply_generic_perform_entry


def _v(field: int, value: int) -> dict:
    return {"field": field, "wire": 0, "value": value}


def _text(field: int, value: str) -> dict:
    return {"field": field, "wire": 2, "text": value}


def _sub(field: int, fields: list[dict]) -> dict:
    return {"field": field, "wire": 2, "sub": {"fields": fields}}


def test_generic_cmd_failed_uses_schema_field_and_reason():
    out = {}
    entry = {"fields": [_v(1, 31), _sub(40, [_v(1, 7)])]}

    apply_generic_perform_entry(out, 31, entry)

    assert out == {
        "kind": "cmd_failed",
        "schema_field": 40,
        "field_1": 7,
        "failed_reason": 7,
    }


def test_generic_use_item_extracts_common_payload_fields():
    out = {}
    entry = {"fields": [_v(1, 14), _sub(19, [_v(1, 101), _v(2, 202), _v(3, 9001)])]}

    apply_generic_perform_entry(out, 14, entry)

    assert out["kind"] == "use_item"
    assert out["schema_field"] == 19
    assert out["caster_id"] == 101
    assert out["target_id"] == 202
    assert out["item_id"] == 9001


def test_unknown_perform_preserves_raw_values_and_text():
    out = {}
    entry = {"fields": [_v(1, 999), _v(2, (1 << 64) - 2), _text(3, "未知")]}

    apply_generic_perform_entry(out, 999, entry)

    assert out["kind"] == "unhandled_battle_perform"
    assert out["perform_type"] == 999
    assert out["raw_fields"] == {"field_1": 999, "field_2": -2, "field_3_text": "未知"}
