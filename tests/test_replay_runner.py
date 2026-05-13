"""Integration tests for BattleReplayRunner — backend self-contained replay."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analysis.replay_runner import BattleReplayRunner
from tests.packet_reader import load_battle_packets

SESSION2_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_2"


# ---------------------------------------------------------------------------
# Basic
# ---------------------------------------------------------------------------


class TestReplayRunnerBasic:
    def test_returns_result(self, session1_runner_result):
        assert session1_runner_result is not None
        assert session1_runner_result.total_packets > 0

    def test_all_events_have_state_snapshots(self, session1_runner_result):
        for ev in session1_runner_result.events:
            assert isinstance(ev.state_before, dict)
            assert isinstance(ev.state_after, dict)

    def test_final_state_matches_baseline(self, session1_runner_result, session1_baseline_result):
        _, baseline_state = session1_baseline_result
        assert session1_runner_result.final_state["round"] == baseline_state["round"]
        assert session1_runner_result.final_state["result"] == baseline_state["result"]
        assert len(session1_runner_result.final_state.get("my_pets", [])) == len(
            baseline_state.get("my_pets", [])
        )
        assert len(session1_runner_result.final_state.get("opp_pets", [])) == len(
            baseline_state.get("opp_pets", [])
        )

    def test_stopped_early_default_false(self, session1_runner_result):
        assert session1_runner_result.stopped_early is False

    def test_stop_round(self, session1_packets):
        runner = BattleReplayRunner()
        result = runner.run(session1_packets, stop_round=5)
        assert result.stopped_early is True
        assert result.total_packets < len(session1_packets)
        max_round = max(e.round_num for e in result.events)
        assert max_round <= 5


# ---------------------------------------------------------------------------
# Per-round
# ---------------------------------------------------------------------------


class TestReplayRunnerPerRound:
    def test_rounds_populated(self, session1_runner_result):
        assert len(session1_runner_result.rounds) > 0

    def test_each_round_has_state(self, session1_runner_result):
        for rs in session1_runner_result.rounds:
            if rs.round_num == 0:
                continue
            assert isinstance(rs.state_at_end, dict)

    def test_round_numbers_sequential(self, session1_runner_result):
        nums = [rs.round_num for rs in session1_runner_result.rounds]
        assert nums == sorted(nums)

    def test_hp_decreases_in_damage_rounds(self, session1_runner_result):
        for rs in session1_runner_result.rounds:
            if rs.round_num < 2:
                continue
            opp_after = rs.state_at_end.get("opp_active")
            if not opp_after:
                continue
            hp = opp_after.get("current_hp", opp_after.get("hp"))
            max_hp = opp_after.get("max_hp", 1)
            if hp is not None and max_hp > 0:
                assert 0 <= hp <= max_hp


# ---------------------------------------------------------------------------
# Damage predictions
# ---------------------------------------------------------------------------


class TestReplayRunnerDamagePrediction:
    def test_predictions_present(self, session1_runner_result):
        total = sum(len(rs.damage_predictions) for rs in session1_runner_result.rounds)
        assert total > 0

    def test_predictions_have_required_fields(self, session1_runner_result):
        for rs in session1_runner_result.rounds:
            for pred in rs.damage_predictions:
                assert "skill_name" in pred
                assert "expected_damage" in pred
                assert "can_ko" in pred
                assert "effectiveness" in pred

    def test_mid_battle_predictions_non_empty(self, session1_runner_result):
        mid_rounds = [rs for rs in session1_runner_result.rounds if 3 <= rs.round_num <= 8]
        assert len(mid_rounds) > 0
        has_pred = any(rs.damage_predictions for rs in mid_rounds)
        assert has_pred

    def test_battle_advice_has_opp_traits(self, session1_runner_result):
        for ev in session1_runner_result.events:
            if ev.battle_advice:
                assert "opp_traits" in ev.battle_advice
                assert isinstance(ev.battle_advice["opp_traits"], list)
                break
        else:
            pytest.fail("No battle_advice found in replay events")


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


class TestReplayRunnerFormatting:
    def test_formatted_events_present(self, session1_runner_result):
        total = sum(len(ev.formatted_events) for ev in session1_runner_result.events)
        assert total > 0

    def test_no_empty_summaries(self, session1_runner_result):
        for ev in session1_runner_result.events:
            for fe in ev.formatted_events:
                assert fe.get("summary", "").strip() != ""

    def test_formatted_events_are_dicts(self, session1_runner_result):
        for ev in session1_runner_result.events:
            for fe in ev.formatted_events:
                assert isinstance(fe, dict)
                assert "kind" in fe
                assert "summary" in fe
                assert "icon" in fe
                assert "color" in fe


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


class TestReplayRunnerHooks:
    def test_hook_advice_collected(self, session1_runner_result):
        total = sum(len(ev.hook_advice) for ev in session1_runner_result.events)
        assert total > 0

    def test_hook_advice_structure(self, session1_runner_result):
        for ev in session1_runner_result.events:
            for ha in ev.hook_advice:
                assert "hook_id" in ha
                assert "title" in ha
                assert "priority" in ha

    def test_lifecycle_hooks(self, session1_runner_result):
        opcodes_seen = {ev.opcode for ev in session1_runner_result.events}
        assert 0x1316 in opcodes_seen
        assert 0x132C in opcodes_seen


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestReplayRunnerSerialization:
    def test_state_dicts_json_serializable(self, session1_runner_result):
        for ev in session1_runner_result.events[:5]:
            json.dumps(ev.state_before, default=str)
            json.dumps(ev.state_after, default=str)

    def test_formatted_events_json_serializable(self, session1_runner_result):
        for ev in session1_runner_result.events[:5]:
            json.dumps(ev.formatted_events)

    def test_damage_predictions_json_serializable(self, session1_runner_result):
        for rs in session1_runner_result.rounds:
            if rs.damage_predictions:
                json.dumps(rs.damage_predictions)
                break

    def test_hook_advice_json_serializable(self, session1_runner_result):
        for ev in session1_runner_result.events:
            if ev.hook_advice:
                json.dumps(ev.hook_advice)
                break

    def test_battle_summary_serializable(self, session1_runner_result):
        json.dumps(session1_runner_result.battle_summary, default=str)


# ---------------------------------------------------------------------------
# Session 2
# ---------------------------------------------------------------------------


class TestReplayRunnerSession2:
    @pytest.fixture(scope="class")
    def session2_result(self):
        if not SESSION2_DIR.exists():
            pytest.skip("battle_session_2 not found")
        pkts = load_battle_packets(SESSION2_DIR)
        if not pkts:
            pytest.skip("No battle packets in session 2")
        runner = BattleReplayRunner()
        return runner.run(pkts)

    def test_basic_result(self, session2_result):
        assert session2_result.total_packets > 0

    def test_final_state_has_pets(self, session2_result):
        assert len(session2_result.final_state.get("my_pets", [])) > 0
        assert len(session2_result.final_state.get("opp_pets", [])) > 0

    def test_formatted_events(self, session2_result):
        total = sum(len(ev.formatted_events) for ev in session2_result.events)
        assert total > 0

    def test_serializable(self, session2_result):
        json.dumps(session2_result.battle_summary, default=str)


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


class TestReplayRunnerSuggestions:
    def test_suggestions_captured_per_event(self, session1_runner_result):
        total = sum(len(ev.suggestions) for ev in session1_runner_result.events)
        assert total > 0

    def test_suggestions_structure(self, session1_runner_result):
        for ev in session1_runner_result.events:
            for sug in ev.suggestions:
                assert isinstance(sug, dict)
                assert "type" in sug
                assert "message" in sug

    def test_round_suggestions_aggregated(self, session1_runner_result):
        total_per_round = sum(len(rs.suggestions) for rs in session1_runner_result.rounds)
        total_per_event = sum(len(ev.suggestions) for ev in session1_runner_result.events)
        assert total_per_round == total_per_event

    def test_suggestions_json_serializable(self, session1_runner_result):
        for ev in session1_runner_result.events:
            if ev.suggestions:
                json.dumps(ev.suggestions)
                break


# ---------------------------------------------------------------------------
# Round-level formatted events
# ---------------------------------------------------------------------------


class TestReplayRunnerRoundFormattedEvents:
    def test_round_formatted_events_present(self, session1_runner_result):
        total = sum(len(rs.formatted_events) for rs in session1_runner_result.rounds)
        total_ev = sum(len(ev.formatted_events) for ev in session1_runner_result.events)
        assert total == total_ev

    def test_round_formatted_events_structure(self, session1_runner_result):
        for rs in session1_runner_result.rounds:
            for fe in rs.formatted_events:
                assert isinstance(fe, dict)
                assert "kind" in fe
                assert "summary" in fe


# ---------------------------------------------------------------------------
# Flags: disable stages
# ---------------------------------------------------------------------------


class TestReplayRunnerFlags:
    def test_no_analysis(self, session1_packets):
        runner = BattleReplayRunner(include_analysis=False)
        result = runner.run(session1_packets)
        for ev in result.events:
            assert ev.battle_advice is None
        for rs in result.rounds:
            assert rs.battle_advice is None
            assert rs.damage_predictions == []

    def test_no_hooks(self, session1_packets):
        runner = BattleReplayRunner(include_hooks=False)
        result = runner.run(session1_packets)
        for ev in result.events:
            assert ev.hook_advice == []

    def test_no_formatting(self, session1_packets):
        runner = BattleReplayRunner(include_formatting=False)
        result = runner.run(session1_packets)
        for ev in result.events:
            assert ev.formatted_events == []
        for rs in result.rounds:
            assert rs.formatted_events == []

    def test_state_only(self, session1_packets):
        runner = BattleReplayRunner(
            include_analysis=False,
            include_hooks=False,
            include_formatting=False,
        )
        result = runner.run(session1_packets)
        assert result.total_packets > 0
        assert result.final_state["round"] > 0
