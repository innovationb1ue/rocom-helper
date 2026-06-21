"""Opcode registry and dispatch helper tests."""
from __future__ import annotations

from types import SimpleNamespace

from src.protocol import opcode_dispatch, opcode_registry, opcodes


def test_opcodes_public_module_uses_shared_registries():
    assert opcodes._OPCODE_REGISTRY is opcode_registry.OPCODE_REGISTRY
    assert opcodes._INNER_REGISTRY is opcode_registry.INNER_REGISTRY
    assert opcodes._OPCODE_REGISTRY[0x1316][0] == "battle_enter"
    assert opcodes._INNER_REGISTRY[390][0] == "inner390_pair"


def test_opcode_from_record_supports_object_mapping_and_int():
    assert opcode_dispatch.opcode_from_record(SimpleNamespace(opcode=0x1316)) == 0x1316
    assert opcode_dispatch.opcode_from_record({"opcode": 0x1324}) == 0x1324
    assert opcode_dispatch.opcode_from_record(0x132C) == 0x132C


def test_summarize_record_dispatches_inner_message():
    def handler(record, inner):
        return {"seen": (record["opcode"], inner["message_id"])}

    kind, payload = opcode_dispatch.summarize_record(
        {"opcode": 0x0414},
        {"message_id": 7},
        opcode_registry={},
        inner_registry={7: ("inner_kind", handler)},
        pb_meta_loader=lambda _opcode: None,
    )

    assert kind == "inner_kind"
    assert payload == {"seen": (0x0414, 7)}


def test_summarize_record_dispatches_main_opcode():
    def handler(record, inner):
        return {"detail": {"opcode": record["opcode"], "inner": inner}}

    kind, payload = opcode_dispatch.summarize_record(
        {"opcode": 0x1334},
        None,
        opcode_registry={0x1334: ("emoji", handler)},
        inner_registry={},
        pb_meta_loader=lambda _opcode: None,
    )

    assert kind == "emoji"
    assert payload == {"detail": {"opcode": 0x1334, "inner": None}}


def test_summarize_record_uses_pb_meta_fallback():
    kind, payload = opcode_dispatch.summarize_record(
        {"opcode": 0x0101},
        None,
        opcode_registry={},
        inner_registry={},
        pb_meta_loader=lambda _opcode: {"message": "ZoneLoginReq", "type": "Req"},
    )

    assert kind == "ZoneLoginReq"
    assert payload == {"opcode": 0x0101, "pb_type": "Req"}


def test_make_detail_handler_keeps_legacy_payload_shape():
    handler = opcode_registry.make_detail_handler(lambda record: {"opcode": record["opcode"]})

    assert handler({"opcode": 1}, None) == {"detail": {"opcode": 1}}
