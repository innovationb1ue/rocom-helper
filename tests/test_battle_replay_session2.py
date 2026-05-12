"""Integration test: replay battle_session_2 (2026-05-08 21:12 ~ 21:18 PvP) through the full pipeline."""
from __future__ import annotations

import pytest
from pathlib import Path

from src.protocol.proto_core import extract_state_wrappers_from_record, extract_inner_message
from src.analysis.battle_state import BattleStateTracker
from src.analysis.battle_processor import compute_battle_summary
from src.analysis.event_formatter import format_battle_event
from tests.packet_reader import load_battle_packets, replay_battle, BATTLE_OPCODES

SESSION_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_2"


@pytest.fixture(scope="module")
def battle_packets():
    return load_battle_packets(SESSION_DIR)


@pytest.fixture(scope="module")
def replay_result(battle_packets):
    return replay_battle(battle_packets)


# ---------------------------------------------------------------------------
# TestPacketLoading
# ---------------------------------------------------------------------------


class TestPacketLoading:
    def test_packets_loaded(self, battle_packets):
        assert len(battle_packets) > 0, "No battle packets loaded from session 2"

    def test_all_records_valid(self, battle_packets):
        for item in battle_packets:
            assert item["record"] is not None, f"parse_record returned None for {item['filename']}"

    def test_all_opcodes_known(self, battle_packets):
        unknown = [item for item in battle_packets if item["opcode"] not in BATTLE_OPCODES]
        assert not unknown, f"Unexpected opcodes: {[(i['filename'], hex(i['opcode'])) for i in unknown]}"


# ---------------------------------------------------------------------------
# TestBattleStructure — verify the battle has correct structure
# ---------------------------------------------------------------------------


class TestBattleStructure:
    def test_battle_enter_present(self, battle_packets):
        enter = [p for p in battle_packets if p["opcode"] == 0x1316]
        assert len(enter) == 1, f"Expected 1 battle_enter, got {len(enter)}"

    def test_battle_finish_present(self, battle_packets):
        finish = [p for p in battle_packets if p["opcode"] == 0x132C]
        assert len(finish) == 1, f"Expected 1 battle_finish, got {len(finish)}"

    def test_has_round_starts(self, battle_packets):
        rs = [p for p in battle_packets if p["opcode"] == 0x131A]
        assert len(rs) > 0, "No round_start packets"

    def test_has_action_resolve(self, battle_packets):
        ar = [p for p in battle_packets if p["opcode"] == 0x1324]
        assert len(ar) > 0, "No action_resolve packets"

    def test_wrappers_have_side(self, battle_packets):
        enter = next(p for p in battle_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter["record"])
        for w in wrappers:
            assert w.get("side") is not None, f"Wrapper missing side: {w.get('name')}"


# ---------------------------------------------------------------------------
# TestBattleStateReplay — full state replay
# ---------------------------------------------------------------------------


class TestBattleStateReplaySession2:
    def test_battle_id_set(self, replay_result):
        _, state = replay_result
        assert state["battle_id"] is not None, "battle_id not set"

    def test_my_pets_populated(self, replay_result):
        _, state = replay_result
        assert len(state["my_pets"]) >= 3, f"Expected >= 3 my_pets, got {len(state['my_pets'])}"

    def test_opp_pets_populated(self, replay_result):
        _, state = replay_result
        assert len(state["opp_pets"]) >= 3, f"Expected >= 3 opp_pets, got {len(state['opp_pets'])}"

    def test_battle_result(self, replay_result):
        _, state = replay_result
        assert state["result"] is not None, f"Battle result not set"

    def test_rounds_tracked(self, replay_result):
        _, state = replay_result
        assert state["round"] > 0, "Round not incremented"

    def test_events_collected(self, replay_result):
        _, state = replay_result
        assert len(state["events"]) >= 50, f"Too few events: {len(state['events'])}"

    def test_active_pets_set(self, replay_result):
        _, state = replay_result
        assert state["my_active"] is not None, "my_active not set"
        assert state["opp_active"] is not None, "opp_active not set"

    def test_player_pets_valid_hp(self, replay_result):
        _, state = replay_result
        for p in state["my_pets"]:
            assert p["max_hp"] > 0, f"Pet {p['name']} has no max_hp"
            assert p["current_hp"] >= 0, f"Pet {p['name']} has negative hp"

    def test_opponent_pets_valid_hp(self, replay_result):
        _, state = replay_result
        for p in state["opp_pets"]:
            assert p["max_hp"] > 0 or p["current_hp"] >= 0, f"Pet {p['name']} has invalid state"


# ---------------------------------------------------------------------------
# TestEventFormatterReplaySession2
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def formatted_replay(replay_result):
    events, state = replay_result
    all_formatted = []
    for e in events:
        opcode = e["opcode"]
        detail = e["detail"]
        current_state = e["state"]
        round_num = current_state.get("round", 0)
        formatted = format_battle_event(opcode, detail, current_state, round_num)
        all_formatted.extend(formatted)
    return all_formatted, state


class TestEventFormatterSession2:
    def test_formatted_events_produced(self, formatted_replay):
        formatted, _ = formatted_replay
        assert len(formatted) > 0, "No formatted events produced"

    def test_no_empty_summaries(self, formatted_replay):
        formatted, _ = formatted_replay
        empty = [fe for fe in formatted if not fe.summary.strip()]
        assert not empty, f"{len(empty)} events have empty summaries"

    def test_battle_enter_event(self, formatted_replay):
        formatted, _ = formatted_replay
        enter = [fe for fe in formatted if fe.kind == "battle_enter"]
        assert len(enter) == 1
        assert enter[0].detail.get("battle_id") is not None

    def test_battle_finish_event(self, formatted_replay):
        formatted, _ = formatted_replay
        finish = [fe for fe in formatted if fe.kind == "battle_finish"]
        assert len(finish) == 1
        assert finish[0].detail["result"] is not None

    def test_damage_events(self, formatted_replay):
        formatted, _ = formatted_replay
        damage = [fe for fe in formatted if fe.kind == "damage"]
        assert len(damage) > 0, "No damage events"
        for ev in damage:
            assert isinstance(ev.detail["damage"], int)
            assert ev.detail["damage"] > 0

    def test_skill_cast_events(self, formatted_replay):
        formatted, _ = formatted_replay
        skill = [fe for fe in formatted if fe.kind == "skill_cast"]
        assert len(skill) > 0, "No skill_cast events"

    def test_round_start_events(self, formatted_replay):
        formatted, _ = formatted_replay
        rounds = [fe for fe in formatted if fe.kind == "round_start"]
        assert len(rounds) > 0, "No round_start events"

    def test_all_colors_valid(self, formatted_replay):
        formatted, _ = formatted_replay
        valid = {"green", "red", "blue", "gold", "gray", "purple", "cyan", "geekblue"}
        bad = [fe for fe in formatted if fe.color not in valid]
        assert not bad, f"Invalid colors: {set(fe.color for fe in bad)}"


# ---------------------------------------------------------------------------
# TestBattleSummarySession2
# ---------------------------------------------------------------------------


class TestBattleSummarySession2:
    def test_summary_computed(self, replay_result):
        _, state = replay_result
        summary = compute_battle_summary(state)
        assert summary["result"] is not None
        assert summary["rounds"] > 0

    def test_summary_pet_counts(self, replay_result):
        _, state = replay_result
        summary = compute_battle_summary(state)
        assert len(summary["my_pets_final"]) == len(state["my_pets"])
        assert len(summary["opp_pets_final"]) == len(state["opp_pets"])

    def test_summary_final_hp_valid(self, replay_result):
        _, state = replay_result
        summary = compute_battle_summary(state)
        for p in summary["my_pets_final"] + summary["opp_pets_final"]:
            assert p["hp"] >= 0
            assert p["status"] in ("存活", "战败")

    def test_summary_event_stats(self, replay_result):
        _, state = replay_result
        summary = compute_battle_summary(state)
        assert len(summary["event_stats"]) > 0
        total = sum(summary["event_stats"].values())
        assert total == len(state["events"])


# ---------------------------------------------------------------------------
# TestBattleReportGenerationSession2 — generate a readable report
# ---------------------------------------------------------------------------


class TestBattleReportSession2:
    def test_generate_report(self, replay_result):
        from scripts.generate_battle_report import generate_report
        report = generate_report(SESSION_DIR)
        assert len(report) > 200, "Report is too short"
        assert "对战开始" in report
        assert "对战结束" in report
        assert "我方阵容" in report
        assert "敌方阵容" in report
        assert "事件统计" in report

    def test_report_saved(self, replay_result, tmp_path):
        from scripts.generate_battle_report import generate_report
        report = generate_report(SESSION_DIR)
        out = tmp_path / "battle_session_2_report.txt"
        out.write_text(report, encoding="utf-8")
        assert out.exists()
        assert out.stat().st_size > 200
