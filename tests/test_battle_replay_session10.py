"""battle_session_10 实战回归测试。"""
from __future__ import annotations

import json

from src.analysis.damage_audit import build_damage_audit, build_damage_mechanism_report
from src.analysis.reflect_effects import build_reflect_candidate_effects
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
                    "base_power": breakdown.get("base_power"),
                    "final_power": breakdown.get("final_power"),
                    "buff_power_flat": (breakdown.get("buff_power_modifiers") or {}).get("flat"),
                    "power_source": breakdown.get("power_source"),
                    "matched_target_key": server_runtime.get("matched_target_key"),
                }

        assert powers[5] == {
            "base_power": 75,
            "final_power": 105,
            "buff_power_flat": 30.0,
            "power_source": "skill_config",
            "matched_target_key": "406",
        }
        assert powers[10] == {
            "base_power": 75,
            "final_power": 125,
            "buff_power_flat": 50.0,
            "power_source": "skill_config",
            "matched_target_key": "405",
        }

    def test_leader_skill_pool_arrives_before_reflect_selection(self, session10_runner_result):
        """首领化确认包应在选择折射前同步真实 7 技能池。"""
        ack_event = next(event for event in session10_runner_result.events if event.index == 76)
        select_reflect_event = next(event for event in session10_runner_result.events if event.index == 78)
        pet_after_ack = next(
            pet for pet in ack_event.state_after["my_pets"]
            if pet.get("name") == "白金独角兽"
        )
        pet_before_reflect = next(
            pet for pet in select_reflect_event.state_before["my_pets"]
            if pet.get("name") == "白金独角兽"
        )

        expected = [7020470, 7050180, 7060130, 7150220, 7030460, 7110200, 7090240]
        internal_ids = {280009, 7000010, 7000030}
        assert [s["skill_id"] for s in pet_after_ack["leader_skill_pool"]] == expected
        assert [s["skill_id"] for s in pet_after_ack["skills"]] == expected
        assert [s["skill_id"] for s in pet_after_ack["equipped_skills"]] == [7020470, 7060130, 7150220, 7050180]
        assert [s["skill_id"] for s in pet_before_reflect["leader_skill_pool"]] == expected
        assert pet_after_ack["leader_skill_pool_source"] == "action_ack.state_wrapper.skill_round_data"
        assert not internal_ids.intersection({s["skill_id"] for s in pet_after_ack["leader_skill_pool"]})

        candidate_ids = {
            item["effect_buff_id"]
            for item in build_reflect_candidate_effects(pet_before_reflect)
        }
        assert {20171870, 20171900, 20171910, 20172000, 20171880, 20171960, 20171940}.issubset(candidate_ids)
        assert 20171890 not in candidate_ids

    def test_reflect_trigger_records_candidates_without_confirming_magic_modifier(self, session10_runner_result):
        """通用折射触发只产生候选效果，不自动确认光加魔攻。"""
        candidate_records = []
        confirmed_light_magic = []
        for event in session10_runner_result.events:
            candidate_records.extend(
                (event.state_after.get("field_context") or {}).get("reflect_candidates") or []
            )
            for pet in event.state_after.get("my_pets", []) + event.state_after.get("opp_pets", []):
                if pet.get("name") != "白金独角兽":
                    continue
                for buff in pet.get("buffs", []):
                    if buff.get("id") == 20890020 and buff.get("derived_buffs"):
                        for child in buff.get("derived_buffs") or []:
                            if child.get("id") == 20171910:
                                confirmed_light_magic.append(child)

        assert any(
            any(item.get("effect_buff_id") == 20171910 for item in record.get("candidate_effects", []))
            for record in candidate_records
        )
        assert not confirmed_light_magic

    def test_zhui_da_breakdown_keeps_reflect_candidates_unconfirmed(self, session10_runner_result):
        """追打预测可审计折射候选，但未确认光加魔攻时不吃魔攻。"""
        found = []
        for round_snapshot in session10_runner_result.rounds:
            for pred in round_snapshot.damage_predictions:
                if pred.get("skill_id") != 7020470:
                    continue
                breakdown = pred.get("damage_breakdown") or {}
                if breakdown.get("reflect_candidate_effects"):
                    found.append(breakdown)

        assert found
        assert found[0]["reflect_buff_applied"] is False
        assert found[0]["attacker_buff_modifiers"].get("spa_up") is None
        assert any(item["effect_buff_id"] == 20171910 for item in found[0]["reflect_candidate_effects"])

    def test_zhui_da_server_power_pilot_applies_to_damage_samples(self, session10_runner_result):
        """追打生产试点应在有服务器目标威力的实战伤害样本上启用。"""
        report = build_damage_audit(session10_runner_result)
        samples = [s for s in report["samples"] if s.get("skill_name") == "追打"]

        assert {s["round_num"] for s in samples if s.get("server_power_applied")} == {6, 9, 10}
        assert [s["server_power_skip_reason"] for s in samples if not s.get("server_power_applied")] == []
        assert sum(s["pct_error"] for s in samples) / len(samples) < 0.30

    def test_damage_mechanism_report_covers_key_unicorn_skills(self, session10_runner_result):
        """机制审计应能反查追打、折射、超级糖果的服务器运行时字段。"""
        report = build_damage_mechanism_report(session10_runner_result, session="battle_session_10")

        zhui_da = [s for s in report["samples"] if s.get("skill_name") == "追打"]
        candy = [s for s in report["samples"] if s.get("skill_name") == "超级糖果"]
        reflect = [s for s in report["samples"] if s.get("skill_name") == "折射"]

        assert zhui_da
        assert {s["round_num"] for s in zhui_da if s.get("server_power_applied")} == {6, 9, 10}
        assert all(s.get("matched_damage_param") is not None for s in zhui_da)
        assert any(s.get("server_power_multiplier") for s in zhui_da)
        assert candy
        assert all("enhance_info" in s for s in candy)
        assert reflect
        assert any(s.get("enhance_info") for s in reflect)
        assert report["recommendations"]["折射"]["status"] == "audit_only"
