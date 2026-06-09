"""Integration tests for BattleReplayRunner — backend self-contained replay."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analysis.replay_models import ReplayEventSnapshot as ModelReplayEventSnapshot
from src.analysis.replay_models import ReplayResult as ModelReplayResult
from src.analysis.replay_runner import BattleReplayRunner, ReplayEventSnapshot, ReplayResult
from src.analysis.damage_audit import (
    build_damage_audit,
    build_damage_calibration,
    build_damage_mechanism_report,
    build_multi_session_damage_audit,
    build_special_damage_rules,
    _ledger_actual_damage,
    _ledger_records_for_damage,
)
from src.analysis.pet_identity import same_battle_pet
from src.protocol.opcodes import summarize
from tests.packet_reader import load_battle_packets

SESSION4_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_4"
SPECTATE1_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "spectate_session_1"


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

    def test_replay_models_are_reexported_for_compatibility(self):
        assert ReplayEventSnapshot is ModelReplayEventSnapshot
        assert ReplayResult is ModelReplayResult

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

    def test_opp_active_matches_one_pet_by_stable_identity(self, session1_runner_result):
        for rs in session1_runner_result.rounds:
            state = rs.state_at_end
            opp_active = state.get("opp_active")
            if not opp_active:
                continue
            matches = [
                p for p in state.get("opp_pets", [])
                if same_battle_pet(p, opp_active)
            ]
            assert len(matches) <= 1, (
                f"round {rs.round_num} active={opp_active.get('name')} "
                f"matched {[p.get('name') for p in matches]}"
            )


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

    def test_attack_predictions_have_damage_values(self, session1_runner_result):
        found_attack = False
        for rs in session1_runner_result.rounds:
            for pred in rs.damage_predictions:
                if pred.get("skill_damage_type") not in (2, 3):
                    continue
                found_attack = True
                assert pred["expected_damage"] is not None
                assert pred["expected_damage"] >= 0
        assert found_attack

    def test_predictions_have_closed_loop_fields(self, session1_runner_result):
        for rs in session1_runner_result.rounds:
            for pred in rs.damage_predictions:
                if pred.get("expected_damage") is None:
                    continue
                assert "prediction" in pred
                assert "explain" in pred
                assert "validation_hint" in pred
                assert pred["prediction"]["total"] >= pred["prediction"]["per_hit"]
                assert isinstance(pred["prediction"]["accuracy_flags"], list)
                return
        pytest.fail("No damage prediction with closed-loop fields found")

    def test_damage_audit_extracts_direct_damage_samples(self, session1_runner_result):
        report = build_damage_audit(session1_runner_result)
        assert report["total_direct_damage"] >= 10
        assert report["matched_predictions"] > 0
        assert report["samples"]
        assert any(s["ledger_ids"] for s in report["samples"])
        assert any(s["actual_source"] != "formatted_event" for s in report["samples"])
        multi_hit = [s for s in report["samples"] if s["hit_count"] > 1]
        assert multi_hit
        assert all(s["actual_total"] >= 0 for s in multi_hit)
        assert report["catastrophic_high_confidence"] == []

    def test_multi_session_damage_audit_groups_by_skill(self, session1_runner_result):
        report = build_damage_audit(session1_runner_result)
        aggregate = build_multi_session_damage_audit({
            "battle_session_1": report,
            "battle_session_1_copy": report,
        })
        assert aggregate["session_count"] == 2
        assert aggregate["total_direct_damage"] == report["total_direct_damage"] * 2
        assert aggregate["matched_predictions"] == report["matched_predictions"] * 2
        assert aggregate["by_skill"]
        assert aggregate["samples"]
        assert aggregate["by_session"]["battle_session_1"]["matched_predictions"] == report["matched_predictions"]

    def test_damage_calibration_generation_filters_and_writes_metrics(self):
        report = {
            "samples": [
                {"skill_id": 1, "predicted_total": 100, "actual_total": 50, "session": "s1"},
                {"skill_id": 1, "predicted_total": 100, "actual_total": 50, "session": "s1"},
                {"skill_id": 1, "predicted_total": 100, "actual_total": 50, "session": "s2"},
                {"skill_id": 2, "predicted_total": 30, "actual_total": 20, "session": "s1"},
                {"skill_id": None, "predicted_total": 10, "actual_total": 5, "session": "s1"},
            ],
        }

        calibration = build_damage_calibration(report)

        assert calibration["version"] == 1
        assert set(calibration["skills"]) == {"1"}
        item = calibration["skills"]["1"]
        assert item["multiplier"] == 0.5
        assert item["sample_count"] == 3
        assert item["source_sessions"] == ["s1", "s2"]
        assert calibration["meta"]["skipped"]["2"] == "sample_count_below_min"

    def test_damage_audit_uses_protocol_damage_for_overkill_hits(self):
        ledger = [
            {"ledger_id": "a", "event_kind": "damage", "skill_name": "追打",
             "hp_before": 0, "hp_after": 0, "actual_damage": 112},
        ]
        detail = {"ledger_ids": ["a"], "ledger_id": "a", "skill_name": "追打"}

        records = _ledger_records_for_damage({"field_context": {"damage_ledger": ledger}}, detail)

        assert [r["ledger_id"] for r in records] == ["a"]
        assert _ledger_actual_damage(records[0]) == 112

    def test_special_damage_rule_generation_excludes_reflect(self):
        report = {
            "samples": [
                {"session": "s1", "skill_id": 7060130, "skill_name": "折射",
                 "round_num": 1, "actual_per_hit": 12, "actual_total": 48,
                 "hit_count": 4, "ledger_ids": ["a"], "target_side": "敌方"},
                {"session": "s1", "skill_id": 7060130, "skill_name": "折射",
                 "round_num": 2, "actual_per_hit": 12, "actual_total": 48,
                 "hit_count": 4, "ledger_ids": ["b"], "target_side": "敌方"},
            ],
        }

        rules = build_special_damage_rules(report)

        assert rules["skills"] == {}
        assert rules["meta"]["excluded_skill_ids"] == [7060130]
        assert "light special damage" in rules["meta"]["excluded_reasons"]["7060130"]

    def test_damage_mechanism_report_uses_state_before_runtime(self):
        state_before = {
            "my_active": {
                "pet_id": 1,
                "name": "测试方",
                "skill_runtime": {
                    "1001": {
                        "raw_damage": 90,
                        "rule_damage_param": 10,
                        "effect_damage_param": 0,
                        "buff_damage_param": 5,
                        "ex_damage_param": 0,
                        "damage_param_result": 105,
                        "damage_params_by_pet": {"401": 105},
                        "restraint_types_by_pet": {"401": 1},
                        "damage_type": 3,
                        "cost_energy_result": 2,
                        "set_cost_info": [{"reason_id": 7, "cost": 2}],
                        "skill_buff": {"damage_param": 5},
                    },
                },
            },
            "my_pets": [],
            "opp_pets": [],
        }
        state_after = {
            **state_before,
            "my_active": {
                **state_before["my_active"],
                "skill_runtime": {
                    "1001": {
                        **state_before["my_active"]["skill_runtime"]["1001"],
                        "raw_damage": 999,
                    },
                },
            },
            "field_context": {
                "damage_ledger": [
                    {
                        "ledger_id": "l1",
                        "event_kind": "damage",
                        "skill_id": 1001,
                        "skill_name": "测试技能",
                        "target_pet_id": 401,
                        "actual_damage": 120,
                    },
                ],
            },
        }
        event = ReplayEventSnapshot(
            index=1,
            opcode=0x1324,
            kind="action_resolve",
            round_num=1,
            state_before=state_before,
            state_after=state_after,
            formatted_events=[
                {
                    "kind": "damage",
                    "detail": {
                        "target_side": "敌方",
                        "target_pet_id": 401,
                        "ledger_id": "l1",
                        "skill_name": "测试技能",
                    },
                },
            ],
            battle_advice={
                "skill_analysis": [
                    {
                        "skill_id": 1001,
                        "skill_name": "测试技能",
                        "prediction": {"total": 110, "per_hit": 110},
                        "damage_breakdown": {
                            "base_power": 100,
                            "final_power": 110,
                            "runtime_power": 105,
                            "power_source": "skill_config",
                            "effectiveness_source": "server_restraint_types",
                            "server_power_applied": False,
                            "server_runtime": {
                                "matched_target_key": "401",
                                "power_source": "server_damage_params",
                                "display_effectiveness": 1.5,
                                "calc_effectiveness": 1.5,
                            },
                        },
                    },
                ],
            },
        )

        report = build_damage_mechanism_report(ReplayResult(total_packets=1, events=[event]), session="s1")
        sample = report["samples"][0]

        assert sample["session"] == "s1"
        assert sample["runtime_state_source"] == "state_before"
        assert sample["raw_damage"] == 90
        assert sample["matched_damage_param"] == 105
        assert sample["restraint_type"] == 1
        assert sample["decomposition_total"] == 105
        assert sample["decomposition_matches"] is True
        assert sample["strategy_totals"]["damage_param_as_effective_power"] == 105
        assert report["recommendations"]["测试技能"]["status"] == "insufficient_samples"

    def test_damage_mechanism_report_falls_back_to_state_after_runtime(self):
        runtime = {
            "raw_damage": 40,
            "rule_damage_param": 0,
            "effect_damage_param": 0,
            "buff_damage_param": 0,
            "ex_damage_param": 0,
            "damage_params_by_pet": {"401": 40},
            "restraint_types_by_pet": {"401": 0},
        }
        event = ReplayEventSnapshot(
            index=1,
            opcode=0x1324,
            kind="action_resolve",
            round_num=1,
            state_before={"my_active": {"pet_id": 1, "skill_runtime": {}}, "my_pets": [], "opp_pets": []},
            state_after={
                "my_active": {"pet_id": 1, "skill_runtime": {"1002": runtime}},
                "my_pets": [],
                "opp_pets": [],
                "field_context": {"damage_ledger": []},
            },
            formatted_events=[
                {
                    "kind": "damage",
                    "detail": {
                        "target_side": "敌方",
                        "target_pet_id": 401,
                        "damage": 30,
                        "skill_name": "后置同步",
                    },
                },
            ],
            battle_advice={
                "skill_analysis": [
                    {
                        "skill_id": 1002,
                        "skill_name": "后置同步",
                        "prediction": {"total": 35, "per_hit": 35},
                        "damage_breakdown": {"base_power": 40, "final_power": 40},
                    },
                ],
            },
        )

        report = build_damage_mechanism_report(ReplayResult(total_packets=1, events=[event]))
        sample = report["samples"][0]

        assert sample["runtime_state_source"] == "state_after"
        assert sample["matched_damage_param"] == 40
        assert sample["decomposition_matches"] is True


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

    def test_messages_json_serializable(self, session1_runner_result):
        json.dumps(session1_runner_result.messages, default=str)


# ---------------------------------------------------------------------------
# Browser parity
# ---------------------------------------------------------------------------


class TestReplayRunnerBrowserParity:
    def test_message_sequence_contains_browser_payloads(self, session1_runner_result):
        msg_types = {msg["type"] for msg in session1_runner_result.messages}
        assert "state_update" in msg_types
        assert "skill_analysis" in msg_types
        assert "hook_advice" in msg_types
        assert "suggestions" in msg_types
        assert "battle_summary" in msg_types
        assert "tactical_recommendations" in msg_types

    def test_round_8_contains_tactical_and_opponent_skill_analysis(self, session1_runner_result):
        rs = next(round_ for round_ in session1_runner_result.rounds if round_.round_num == 8)
        assert rs.tactical_recommendations is not None
        assert rs.opp_skill_source in {"protocol", "used", "preset"}
        assert rs.opp_skill_analysis

    def test_round_17_contains_tactical_and_opponent_skill_analysis(self, session1_runner_result):
        rs = next(round_ for round_ in session1_runner_result.rounds if round_.round_num == 17)
        assert rs.tactical_recommendations is not None
        assert rs.opp_skill_analysis

    def test_no_unknown_skill_names_in_replay_outputs(self, session1_runner_result):
        for rs in session1_runner_result.rounds:
            for pred in rs.damage_predictions + rs.opp_skill_analysis:
                assert pred.get("skill_name")
                assert pred["skill_name"] != "?"
                assert "未知技能" not in pred["skill_name"]

    def test_internal_event_kinds_are_not_exposed_directly(self, session1_runner_result):
        all_kinds = [
            fe["kind"]
            for rs in session1_runner_result.rounds
            for fe in rs.formatted_events
        ]
        assert "pvp_perform_marker" not in all_kinds
        assert "supply_pet" not in all_kinds

    def test_tactical_damage_is_reasonable(self, session1_runner_result):
        rs = next(round_ for round_ in session1_runner_result.rounds if round_.round_num == 8)
        skill_actions = [
            action for action in rs.tactical_recommendations.get("actions", [])
            if action.get("action_type") == "skill" and action.get("damage_dealt") is not None
        ]
        assert skill_actions
        assert max(action["damage_dealt"] for action in skill_actions) < 1000

    def test_tactical_recommendations_include_reliability_and_cockpit_fields(self, session1_runner_result):
        rs = next(round_ for round_ in session1_runner_result.rounds if round_.round_num == 8)
        rec = rs.tactical_recommendations
        assert rec is not None
        assert rec.get("primary_plan")
        assert rec.get("metrics", {}).get("speed_line")
        assert rec.get("opponent_profile", {}).get("skill_source") in {"protocol", "used", "preset"}
        reliability = rec.get("reliability")
        assert reliability is not None
        assert reliability["confidence"] in {"high", "medium", "low"}
        assert isinstance(reliability["missing_reasons"], list)
        action = rec["actions"][0]
        assert action.get("expected_gain")
        assert action.get("risk")
        assert action.get("metrics")


class TestReplayRunnerFieldContext:
    def _weather_subset(self, packets):
        subset = []
        weather_count = 0
        for item in packets:
            if item["opcode"] == 0x1316 and not subset:
                subset.append(item)
                continue
            if item["opcode"] != 0x1324:
                continue
            _, payload = summarize(item["record"])
            detail = payload.get("detail", payload) if isinstance(payload, dict) else {}
            entries = detail.get("entries", []) if isinstance(detail, dict) else []
            if any(entry.get("kind") == "weather_change" for entry in entries):
                subset.append(item)
                weather_count += sum(1 for entry in entries if entry.get("kind") == "weather_change")
        return subset, weather_count

    @pytest.mark.parametrize("session_dir", [SESSION4_DIR, SPECTATE1_DIR])
    def test_real_weather_changes_are_recorded_in_history(self, session_dir):
        if not session_dir.exists():
            pytest.skip(f"{session_dir.name} not found")
        packets, expected_weather_changes = self._weather_subset(load_battle_packets(session_dir))
        assert expected_weather_changes > 0
        runner = BattleReplayRunner(
            include_analysis=False,
            include_hooks=False,
            include_formatting=False,
        )
        result = runner.run(packets)
        history = result.final_state.get("field_context", {}).get("weather_history", [])
        weather_changes = [
            event for event in result.final_state.get("field_context", {}).get("global_events", [])
            if event.get("kind") == "weather_change"
        ]
        assert weather_changes
        assert len(weather_changes) == expected_weather_changes
        assert len(history) >= len(weather_changes)
        assert all(item.get("name") for item in history)
        assert result.battle_summary["weather_history"] == history
        assert result.battle_summary["global_event_stats"]["weather_change"] == len(weather_changes)

    def test_state_update_messages_include_field_context(self, session1_runner_result):
        state_messages = [
            msg for msg in session1_runner_result.messages
            if msg.get("type") == "state_update"
        ]
        assert state_messages
        assert "field_context" in state_messages[-1]["state"]

    def test_sync_context_and_skill_runtime_recorded(self, session1_runner_result):
        """真实回放应记录紧凑同步历史和技能运行时参数。"""
        state = session1_runner_result.final_state
        ctx = state.get("field_context", {})
        assert ctx.get("sync_events")
        assert len(ctx["sync_events"]) <= 300
        assert ctx.get("perform_groups")
        assert len(ctx["perform_groups"]) <= 300
        pets = state.get("my_pets", []) + state.get("opp_pets", [])
        runtime_items = [
            item
            for pet in pets
            for item in (pet.get("skill_runtime") or {}).values()
        ]
        assert any(item.get("damage_param_result") is not None for item in runtime_items)
        assert any(item.get("cost_energy_result") is not None for item in runtime_items)
        assert any(item.get("damage_params_by_pet") for item in runtime_items)
        assert any(item.get("restraint_types_by_pet") for item in runtime_items)


# ---------------------------------------------------------------------------
# Session 2
# ---------------------------------------------------------------------------


class TestReplayRunnerSession2:
    def test_basic_result(self, session2_runner_result):
        assert session2_runner_result.total_packets > 0

    def test_final_state_has_pets(self, session2_runner_result):
        assert len(session2_runner_result.final_state.get("my_pets", [])) > 0
        assert len(session2_runner_result.final_state.get("opp_pets", [])) > 0

    def test_formatted_events(self, session2_runner_result):
        total = sum(len(ev.formatted_events) for ev in session2_runner_result.events)
        assert total > 0

    def test_serializable(self, session2_runner_result):
        json.dumps(session2_runner_result.battle_summary, default=str)


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


class TestReplayRunnerSnapshots:
    def test_snapshots_are_stable_after_later_events(self, session1_packets):
        result = BattleReplayRunner(include_analysis=False, include_hooks=False).run(
            session1_packets,
            stop_round=3,
        )
        first_with_pets = next(ev for ev in result.events if ev.state_after.get("my_pets"))
        original_name = first_with_pets.state_after["my_pets"][0]["name"]

        result.final_state["my_pets"][0]["name"] = "__mutated_final_state__"

        assert first_with_pets.state_after is not result.final_state
        assert first_with_pets.state_after["my_pets"][0]["name"] == original_name


# ---------------------------------------------------------------------------
# Flags: disable stages
# ---------------------------------------------------------------------------


class TestReplayRunnerFlags:
    def test_no_analysis(self, session1_packets):
        runner = BattleReplayRunner(include_analysis=False)
        result = runner.run(session1_packets, stop_round=3)
        for ev in result.events:
            assert ev.battle_advice is None
        for rs in result.rounds:
            assert rs.battle_advice is None
            assert rs.damage_predictions == []

    def test_no_hooks(self, session1_packets):
        runner = BattleReplayRunner(include_hooks=False)
        result = runner.run(session1_packets, stop_round=3)
        for ev in result.events:
            assert ev.hook_advice == []

    def test_no_formatting(self, session1_packets):
        runner = BattleReplayRunner(include_formatting=False)
        result = runner.run(session1_packets, stop_round=3)
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
        result = runner.run(session1_packets, stop_round=3)
        assert result.total_packets > 0
        assert result.final_state["round"] > 0
