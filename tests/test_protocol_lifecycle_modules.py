"""战斗生命周期协议提取模块测试。"""
from __future__ import annotations

from src.protocol.battle_parts import lifecycle
from src.protocol.battle_parts.lifecycle_core import (
    BATTLE_RESULT_MAP,
    extract_1316_enter,
    extract_131a_round_start,
    extract_132c_finish,
)
from src.protocol.battle_parts.lifecycle_flow import (
    extract_1312_round_flow,
    extract_1313_round_confirm,
    extract_1314_round_confirm_rsp,
)


def test_lifecycle_core_exports_match_compat_facade(session1_packets):
    enter = next(item["record"] for item in session1_packets if item["opcode"] == 0x1316)
    round_start = next(item["record"] for item in session1_packets if item["opcode"] == 0x131A)
    finish = next(item["record"] for item in session1_packets if item["opcode"] == 0x132C)

    assert BATTLE_RESULT_MAP[66] == "WIN_HP"
    assert extract_1316_enter(enter) == lifecycle.extract_1316_enter(enter)
    assert extract_131a_round_start(round_start) == lifecycle.extract_131a_round_start(round_start)
    assert extract_132c_finish(finish) == lifecycle.extract_132c_finish(finish)


def test_lifecycle_flow_exports_match_compat_facade_for_raw_fallback():
    round_flow_record = {
        "opcode": 0x1312,
        "opcode_hex": "0x1312",
        "root": {"fields": [{"field": 1, "wire": 0, "value": 7}]},
    }
    confirm_record = {
        "opcode": 0x1313,
        "opcode_hex": "0x1313",
        "root": {"fields": [{"field": 2, "wire": 0, "value": 9}]},
    }
    confirm_rsp_record = {
        "opcode": 0x1314,
        "opcode_hex": "0x1314",
        "root": {"fields": [{"field": 3, "wire": 0, "value": 11}]},
    }

    assert extract_1312_round_flow(round_flow_record) == lifecycle.extract_1312_round_flow(round_flow_record)
    assert extract_1313_round_confirm(confirm_record) == lifecycle.extract_1313_round_confirm(confirm_record)
    assert extract_1314_round_confirm_rsp(confirm_rsp_record) == lifecycle.extract_1314_round_confirm_rsp(confirm_rsp_record)
