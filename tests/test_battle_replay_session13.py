"""battle_session_13 新战斗回归测试。"""
from __future__ import annotations

import json

from tests.conftest import SESSION13_DIR


def _pet_by_name(state, name):
    for pet in state["my_pets"] + state["opp_pets"]:
        if pet.get("name") == name:
            return pet
    raise AssertionError(f"Pet not found: {name}")


class TestSession13Fixture:
    def test_metadata_matches_source_battle(self):
        meta = json.loads((SESSION13_DIR / "_session.json").read_text(encoding="utf-8"))

        assert meta["session_id"] == "battle_session_13"
        assert meta["source_session"] == "2026-06-20_18-46-55_monitor"
        assert meta["battle_index"] == 1
        assert meta["enter_file"] == "s2c_0x4013_1102_184801.946.bin"
        assert meta["finish_file"] == "s2c_0x4013_2672_185052.135.bin"
        assert meta["file_count"] > 0


class TestSession13Replay:
    def test_final_state_keeps_switched_out_sonic_dog_alive(self, session13_runner_result):
        state = session13_runner_result.final_state
        defeated = [pet for pet in state["opp_pets"] if pet.get("current_hp") == 0]

        assert state["phase"] == "finished"
        assert state["result"] == "WIN_HP"
        assert len(defeated) == 4
        assert _pet_by_name(state, "音速犬")["current_hp"] == 18

    def test_round6_damage_is_assigned_to_ye_xiao_side_406(self, session13_runner_result):
        round6 = next(rs for rs in session13_runner_result.rounds if rs.round_num == 6)
        state = round6.state_at_end
        sonic_dog = _pet_by_name(state, "音速犬")
        ye_xiao = _pet_by_name(state, "夜枭")

        assert sonic_dog["current_hp"] == 18
        assert ye_xiao["current_hp"] == 0
        assert ye_xiao["slot"] == 406
        assert ye_xiao["last_hp_event"]["side"] == 406

    def test_defeat_events_use_hydrated_pet_names(self, session13_runner_result):
        defeat_summaries = [
            event["summary"]
            for round_snapshot in session13_runner_result.rounds
            for event in round_snapshot.formatted_events
            if event.get("kind") == "defeat"
        ]

        assert "我方 击败了 敌方!" not in defeat_summaries
        assert "我方 击败了 熔岩布丁!" in defeat_summaries
