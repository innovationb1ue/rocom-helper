"""协议字段覆盖回归测试。"""
from __future__ import annotations

import json
from pathlib import Path

from src.protocol.opcodes import summarize
from tests.packet_reader import BATTLE_OPCODES, load_battle_packets


def _schema_messages() -> dict:
    return json.loads(Path("data/game/proto_schema.json").read_text(encoding="utf-8"))["messages"]


def test_schema_field_numbers_match_perform_extractors():
    messages = _schema_messages()
    perform = messages["BattlePerformInfo"]["fields"]
    pet_sync = messages["BattlePetSyncInfo"]["fields"]
    skill_round = messages["PetSkillRoundData"]["fields"]

    assert perform["3"]["name"] == "skill_cast"
    assert perform["5"]["name"] == "buff_trigger"
    assert perform["40"]["name"] == "cmd_failed"
    assert perform["52"]["name"] == "box_shield_break"
    assert pet_sync["11"]["name"] == "original_damage"
    assert pet_sync["12"]["name"] == "damage_change"
    assert pet_sync["13"]["name"] == "damage_result"
    assert skill_round["39"]["name"] == "skill_id"
    assert skill_round["41"]["name"] == "cr_damage_params"
    assert skill_round["59"]["name"] == "set_cost_info"


def test_battle_perform_entries_are_named_across_fixtures():
    unknown = []
    root = Path("tests/fixtures/packets")
    for session_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("battle_session_")):
        for item in load_battle_packets(session_dir):
            if item["opcode"] not in (0x1324, 0x13F3, 0x13FC):
                continue
            _kind, summary = summarize(item["record"])
            detail = summary.get("detail", summary)
            for entry in detail.get("entries", []) if isinstance(detail, dict) else []:
                if entry.get("kind") == "unhandled_battle_perform" and not entry.get("schema_field"):
                    unknown.append((session_dir.name, item["filename"], entry.get("perform_type")))

    assert not unknown


def test_battle_opcode_set_comes_from_constants():
    assert 0x1313 in BATTLE_OPCODES
    assert 0x1314 in BATTLE_OPCODES
    assert 0x1309 in BATTLE_OPCODES
    assert 0x132E in BATTLE_OPCODES
