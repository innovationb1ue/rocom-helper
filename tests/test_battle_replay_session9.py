"""Integration regression tests for battle_session_9."""
from __future__ import annotations

import json

from tests.conftest import SESSION9_DIR
from tests.packet_reader import BATTLE_OPCODES


class TestSession9Fixture:
    def test_metadata_matches_source_battle(self):
        meta = json.loads((SESSION9_DIR / "_session.json").read_text(encoding="utf-8"))

        assert meta["session_id"] == "battle_session_9"
        assert meta["source_session"] == "2026-05-25_22-58-53_monitor"
        assert meta["battle_index"] == 1
        assert meta["enter_file"] == "s2c_0x4013_0664_225921.279.bin"
        assert meta["finish_file"] == "s2c_0x4013_0864_230204.677.bin"
        assert meta["file_count"] > 0

    def test_packets_loaded(self, session9_packets):
        assert len(session9_packets) == 71

    def test_all_records_valid(self, session9_packets):
        for item in session9_packets:
            assert item["record"] is not None, f"parse_record returned None for {item['filename']}"

    def test_all_opcodes_known(self, session9_packets):
        unknown = [item for item in session9_packets if item["opcode"] not in BATTLE_OPCODES]
        assert not unknown, f"Unexpected opcodes: {[(i['filename'], hex(i['opcode'])) for i in unknown]}"


class TestSession9BattleStructure:
    def test_lifecycle_packets_present_once(self, session9_packets):
        enter = [p for p in session9_packets if p["opcode"] == 0x1316]
        finish = [p for p in session9_packets if p["opcode"] == 0x132C]

        assert len(enter) == 1
        assert len(finish) == 1

    def test_has_round_starts_and_actions(self, session9_packets):
        round_starts = [p for p in session9_packets if p["opcode"] == 0x131A]
        action_resolves = [p for p in session9_packets if p["opcode"] == 0x1324]

        assert len(round_starts) > 0
        assert len(action_resolves) > 0


class TestSession9Replay:
    def test_final_state_finished(self, session9_runner_result):
        state = session9_runner_result.final_state

        assert state["phase"] == "finished"
        assert state["result"] == "WIN_HP"
        assert state["round"] == 8

    def test_rosters_populated(self, session9_runner_result):
        state = session9_runner_result.final_state

        assert len(state["my_pets"]) == 6
        assert len(state["opp_pets"]) == 3
        assert state["my_active"] is not None
        assert state["opp_active"] is not None

    def test_runner_produces_rounds_predictions_and_hooks(self, session9_runner_result):
        assert len(session9_runner_result.rounds) == 8

        total_predictions = sum(len(rs.damage_predictions) for rs in session9_runner_result.rounds)
        total_hooks = sum(len(ev.hook_advice) for ev in session9_runner_result.events)

        assert total_predictions > 0
        assert total_hooks > 0

    def test_formatted_events_have_summaries(self, session9_runner_result):
        formatted_events = [
            event
            for snapshot in session9_runner_result.events
            for event in snapshot.formatted_events
        ]

        assert formatted_events
        assert all(event.get("summary", "").strip() for event in formatted_events)
