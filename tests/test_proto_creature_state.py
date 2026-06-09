"""宠物和 state wrapper 提取模块的独立契约测试。"""
from __future__ import annotations

from src.protocol.proto.constants import SDT_TO_TYPE
from src.protocol.proto.creature import extract_creature
from src.protocol.proto.state_wrapper import extract_state_wrappers_from_record
from src.protocol.proto_core import extract_creature as compat_extract_creature
from src.protocol.proto_core import extract_state_wrappers_from_record as compat_extract_state_wrappers_from_record


def test_creature_extractor_matches_proto_core_facade_for_type_mapping():
    name = "测试精灵"
    msg = {
        "fields": [
            {"field": 1, "wire": 0, "offset": 0, "value": 1},
            {"field": 2, "wire": 0, "offset": 0, "value": 1001},
            {"field": 3, "wire": 2, "offset": 0, "text": name, "raw_hex": name.encode().hex()},
            {"field": 6, "wire": 0, "offset": 0, "value": 5},
            {"field": 6, "wire": 0, "offset": 0, "value": 12},
            {"field": 10, "wire": 0, "offset": 0, "value": 50},
        ],
        "consumed": 100,
        "clean": True,
    }
    record = {"opcode": 0x1316, "opcode_hex": "0x1316", "seq": 1}

    creature = extract_creature(msg, path="root.test", record=record)

    assert SDT_TO_TYPE[5] == 2
    assert creature == compat_extract_creature(msg, path="root.test", record=record)
    assert creature["types"] == [2, 7]


def test_state_wrapper_extractor_matches_proto_core_facade_for_battle_enter(session1_packets):
    enter = next(p for p in session1_packets if p["opcode"] == 0x1316)

    wrappers = extract_state_wrappers_from_record(enter["record"])

    assert wrappers == compat_extract_state_wrappers_from_record(enter["record"])
    assert len(wrappers) >= 2
    assert {w.get("side") for w in wrappers} >= {1, 401}
    assert all(w.get("name") for w in wrappers)
    assert all("skill_source" in w for w in wrappers)

