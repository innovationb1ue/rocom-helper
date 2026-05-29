"""battle_session_10 实战回归测试。"""
from __future__ import annotations

import json

from tests.conftest import SESSION10_DIR
from tests.packet_reader import BATTLE_OPCODES


class TestSession10Fixture:
    def test_metadata_matches_source_battle(self):
        meta = json.loads((SESSION10_DIR / "_session.json").read_text(encoding="utf-8"))

        assert meta["session_id"] == "battle_session_10"
        assert meta["source_session"] == "2026-05-28_21-30-31_monitor"
        assert meta["battle_index"] == 1
        assert meta["enter_file"] == "s2c_0x4013_0513_213425.228.bin"
        assert meta["finish_file"] == "s2c_0x4013_0752_213744.998.bin"
        assert meta["file_count"] > 0

    def test_packets_loaded(self, session10_packets):
        assert len(session10_packets) == 157

    def test_all_records_valid(self, session10_packets):
        for item in session10_packets:
            assert item["record"] is not None, f"parse_record returned None for {item['filename']}"

    def test_all_opcodes_known(self, session10_packets):
        unknown = [item for item in session10_packets if item["opcode"] not in BATTLE_OPCODES]
        assert not unknown, f"Unexpected opcodes: {[(i['filename'], hex(i['opcode'])) for i in unknown]}"


class TestSession10Replay:
    def test_final_state_finished(self, session10_runner_result):
        state = session10_runner_result.final_state

        assert state["phase"] == "finished"
        assert state["result"] == "WIN_HP"
        assert state["round"] == 10
        assert len(state["my_pets"]) == 6
        assert len(state["opp_pets"]) == 5

    def test_target_server_power_for_zhui_da(self, session10_runner_result):
        """锁定本场实战中追打对尖嘴狐仙和罗隐目标的服务器威力。"""
        powers = {}
        for round_snapshot in session10_runner_result.rounds:
            if round_snapshot.round_num not in (5, 10):
                continue
            for pred in round_snapshot.damage_predictions:
                if pred.get("skill_id") != 7020470:
                    continue
                breakdown = pred.get("damage_breakdown") or {}
                server_runtime = breakdown.get("server_runtime") or {}
                powers[round_snapshot.round_num] = {
                    "final_power": breakdown.get("final_power"),
                    "power_source": breakdown.get("power_source"),
                    "matched_target_key": server_runtime.get("matched_target_key"),
                }

        assert powers[5] == {
            "final_power": 93,
            "power_source": "server_damage_params",
            "matched_target_key": "406",
        }
        assert powers[10] == {
            "final_power": 103,
            "power_source": "server_damage_params",
            "matched_target_key": "405",
        }
