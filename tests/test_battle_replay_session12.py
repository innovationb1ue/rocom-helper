"""battle_session_12 新战斗回归测试。"""
from __future__ import annotations

import json

from src.analysis.replay_runner import BattleReplayRunner
from tests.conftest import SESSION12_DIR
from tests.packet_reader import BATTLE_OPCODES


def _prediction_by_name(result, skill_name: str):
    for pred in result.rounds[-1].damage_predictions:
        if pred.get("skill_name") == skill_name:
            return pred
    raise AssertionError(f"missing prediction for {skill_name}")


def _accuracy_flags(pred):
    return set((pred.get("prediction") or {}).get("accuracy_flags") or [])


class TestSession12Fixture:
    def test_metadata_matches_source_battle(self):
        meta = json.loads((SESSION12_DIR / "_session.json").read_text(encoding="utf-8"))

        assert meta["session_id"] == "battle_session_12"
        assert meta["source_session"] == "2026-06-10_22-09-19_monitor"
        assert meta["battle_index"] == 1
        assert meta["enter_file"] == "s2c_0x4013_0627_221033.921.bin"
        assert meta["finish_file"] == "s2c_0x4013_1623_221322.122.bin"
        assert meta["file_count"] > 0

    def test_packets_loaded(self, session12_packets):
        assert len(session12_packets) == 157

    def test_all_records_valid(self, session12_packets):
        for item in session12_packets:
            assert item["record"] is not None, f"parse_record returned None for {item['filename']}"

    def test_all_opcodes_known(self, session12_packets):
        unknown = [item for item in session12_packets if item["opcode"] not in BATTLE_OPCODES]
        assert not unknown, f"Unexpected opcodes: {[(i['filename'], hex(i['opcode'])) for i in unknown]}"


class TestSession12Replay:
    def test_final_state_finished(self, session12_runner_result):
        state = session12_runner_result.final_state

        assert state["phase"] == "finished"
        assert state["result"] == "WIN_HP"
        assert state["round"] == 10
        assert len(state["my_pets"]) == 6
        assert len(state["opp_pets"]) == 5

    def test_five_observed_opponent_defeats_are_allowed_until_finish(self, session12_runner_result):
        state = session12_runner_result.final_state
        defeated = [pet for pet in state["opp_pets"] if pet.get("current_hp") == 0]

        assert len(defeated) == 5
        assert state["phase"] == "finished"
        assert state["result"] == "WIN_HP"
        assert state.get("terminal_pending") is False

    def test_observed_defeats_do_not_trigger_settling_without_resource_zero(self, session12_packets):
        result = BattleReplayRunner(include_analysis=False, include_hooks=False).run(
            session12_packets,
            stop_round=9,
        )
        state = result.final_state
        defeated = [pet for pet in state["opp_pets"] if pet.get("current_hp") == 0]

        assert len(defeated) >= 3
        assert state["result"] is None
        assert state["phase"] != "settling"
        assert state.get("terminal_pending") is False
        assert result.stopped_early is True

    def test_stop_round_10_processes_finish_packet_in_same_round(self, session12_packets):
        result = BattleReplayRunner(include_analysis=False, include_hooks=False).run(
            session12_packets,
            stop_round=10,
        )
        state = result.final_state

        assert result.stopped_early is False
        assert state["round"] == 10
        assert state["phase"] == "finished"
        assert state["result"] == "WIN_HP"

    def test_change_pet_uses_base_conf_canonical_name(self, session12_packets):
        result = BattleReplayRunner().run(session12_packets, stop_round=4)
        opp_active = result.final_state["opp_active"]

        assert opp_active["name"] == "岚鸟"
        assert opp_active["protocol_name"] == "翱翔于天"
        assert opp_active["pet_id"] == 410280
        assert opp_active["base_conf_id"] == 3287
        assert opp_active["base_id"] == 3287

    def test_lanniao_used_skills_follow_current_active(self, session12_packets):
        result = BattleReplayRunner().run(session12_packets, stop_round=6)
        opp_active = result.final_state["opp_active"]
        used_names = [skill.get("skill_name") for skill in opp_active.get("used_skills", [])]

        assert opp_active["name"] == "岚鸟"
        assert used_names == ["顺风", "震击", "闪击", "聚能"]
        assert "助燃" not in used_names
        assert "晒太阳" not in used_names

    def test_round2_low_confidence_ko_is_flagged(self, session12_packets):
        result = BattleReplayRunner().run(session12_packets, stop_round=2)
        pred = _prediction_by_name(result, "水幕冲击")

        assert pred["can_ko"] is True
        assert pred["confidence"] == "low"
        assert "runtime_target_unmatched" in _accuracy_flags(pred)
        assert "技能尚未经过回放校准" in pred["validation_hint"]

    def test_round6_reflect_does_not_inherit_multi_hit(self, session12_packets):
        result = BattleReplayRunner().run(session12_packets, stop_round=6)
        pred = _prediction_by_name(result, "折射")

        assert pred["hit_count"] == 1
        assert pred["expected_damage"] == 63
        assert pred["damage_breakdown"]["buff_hit_count_modifiers"] == {}

    def test_round8_zhui_da_target_unmatched_stays_low_confidence(self, session12_packets):
        result = BattleReplayRunner().run(session12_packets, stop_round=8)
        pred = _prediction_by_name(result, "追打")

        assert pred["hit_count"] == 5
        assert pred["confidence"] == "low"
        assert pred["damage_breakdown"]["server_power_applied"] is False
        assert pred["damage_breakdown"]["server_power_skip_reason"] == "target_unmatched"
        assert {"multi_hit", "runtime_target_unmatched"}.issubset(_accuracy_flags(pred))

    def test_round10_zhui_da_keeps_target_unmatched_flags(self, session12_packets):
        result = BattleReplayRunner().run(session12_packets, stop_round=10)
        pred = _prediction_by_name(result, "追打")

        assert pred["hit_count"] == 5
        assert pred["confidence"] == "low"
        assert pred["damage_breakdown"]["server_power_applied"] is False
        assert pred["damage_breakdown"]["server_power_skip_reason"] == "target_unmatched"
        assert {"uncalibrated_skill", "multi_hit", "runtime_target_unmatched"}.issubset(_accuracy_flags(pred))
