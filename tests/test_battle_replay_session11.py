"""battle_session_11 活跃 side 绑定回归测试。"""
from __future__ import annotations

import json

from tests.conftest import SESSION11_DIR
from tests.packet_reader import BATTLE_OPCODES


def _pet_by_name(state, side_key: str, name: str):
    for pet in state[side_key]:
        if pet.get("name") == name:
            return pet
    raise AssertionError(f"{side_key} missing pet {name}")


class TestSession11Fixture:
    def test_metadata_matches_source_battle(self):
        meta = json.loads((SESSION11_DIR / "_session.json").read_text(encoding="utf-8"))

        assert meta["session_id"] == "battle_session_11"
        assert meta["source_session"] == "2026-05-28_22-45-31_monitor"
        assert meta["battle_index"] == 1
        assert meta["enter_file"] == "s2c_0x4013_17069_224600.249.bin"
        assert meta["finish_file"] == "s2c_0x4013_18909_224904.496.bin"
        assert meta["file_count"] > 0

    def test_packets_loaded(self, session11_packets):
        assert len(session11_packets) == 133

    def test_all_records_valid(self, session11_packets):
        for item in session11_packets:
            assert item["record"] is not None, f"parse_record returned None for {item['filename']}"

    def test_all_opcodes_known(self, session11_packets):
        unknown = [item for item in session11_packets if item["opcode"] not in BATTLE_OPCODES]
        assert not unknown, f"Unexpected opcodes: {[(i['filename'], hex(i['opcode'])) for i in unknown]}"


class TestSession11Replay:
    def test_final_state_finished(self, session11_runner_result):
        state = session11_runner_result.final_state

        assert state["phase"] == "finished"
        assert state["result"] == "WIN_HP"
        assert state["round"] == 9
        assert len(state["my_pets"]) == 6
        assert len(state["opp_pets"]) == 5

    def test_generic_side_damage_stays_on_round_start_active(self, session11_runner_result):
        state = session11_runner_result.final_state

        fair_dove = _pet_by_name(state, "my_pets", "公平鸽")
        cheer_crab = _pet_by_name(state, "my_pets", "加油蟹")

        assert fair_dove["current_hp"] == 413
        assert fair_dove["max_hp"] == 413
        assert cheer_crab["current_hp"] == 0
        assert cheer_crab["max_hp"] == 435

    def test_only_active_crab_is_defeated_on_my_side(self, session11_runner_result):
        state = session11_runner_result.final_state
        defeated_names = [
            pet.get("name")
            for pet in state["my_pets"]
            if pet.get("current_hp") == 0
        ]

        assert defeated_names == ["加油蟹"]
