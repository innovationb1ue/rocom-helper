"""battle_session_11 活跃 side 绑定回归测试。"""
from __future__ import annotations

import json

from src.analysis.damage_audit import build_damage_audit
from src.analysis.reflect_effects import build_reflect_candidate_effects
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

    def test_leader_skill_pool_arrives_before_reflect_selection(self, session11_runner_result):
        """session 11 中首领化新增技能也必须在选择折射前进入有效技能池。"""
        ack_event = next(event for event in session11_runner_result.events if event.index == 84)
        select_reflect_event = next(event for event in session11_runner_result.events if event.index == 86)
        pet_after_ack = _pet_by_name(ack_event.state_after, "my_pets", "白金独角兽")
        pet_before_reflect = _pet_by_name(select_reflect_event.state_before, "my_pets", "白金独角兽")

        expected = [7020470, 7050180, 7060130, 7150220, 7030240, 7110250, 7090140]
        internal_ids = {280009, 7000010, 7000030}

        assert [s["skill_id"] for s in pet_after_ack["leader_skill_pool"]] == expected
        assert [s["skill_id"] for s in pet_before_reflect["leader_skill_pool"]] == expected
        assert [s["skill_id"] for s in pet_after_ack["skills"]] == expected
        assert [s["skill_id"] for s in pet_after_ack["equipped_skills"]] == [7020470, 7060130, 7150220, 7050180]
        assert pet_after_ack["leader_skill_pool_source"] == "action_ack.state_wrapper.skill_round_data"
        assert not internal_ids.intersection({s["skill_id"] for s in pet_after_ack["leader_skill_pool"]})

        candidate_ids = {
            item["effect_buff_id"]
            for item in build_reflect_candidate_effects(pet_before_reflect)
        }
        assert {20171870, 20171900, 20171910, 20172000, 20171880, 20171960, 20171940}.issubset(candidate_ids)

    def test_zhui_da_server_power_pilot_skips_without_target_match(self, session11_runner_result):
        """session 11 的追打没有匹配目标 server power 时必须保持原公式。"""
        report = build_damage_audit(session11_runner_result)
        samples = [s for s in report["samples"] if s.get("skill_name") == "追打"]

        assert samples
        assert not any(s.get("server_power_applied") for s in samples)
        assert {s.get("server_power_skip_reason") for s in samples} == {"target_unmatched"}
