"""Integration test: replay real captured battle packets through the full parsing pipeline."""
from __future__ import annotations

import pytest
from pathlib import Path

from src.protocol.proto_core import (
    parse_record,
    extract_inner_message,
    extract_state_wrappers_from_record,
    field_groups,
    collect_varints,
    first_sub,
)
from src.protocol.opcodes import summarize
from src.analysis.battle_state import BattleStateTracker
from src.analysis.battle_processor import compute_battle_summary
from src.analysis.event_formatter import format_battle_event
from tests.packet_reader import (
    read_bin_packet,
    BATTLE_OPCODES,
)

SESSION_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"


# ---------------------------------------------------------------------------
# TestPacketReader
# ---------------------------------------------------------------------------


class TestPacketReader:
    def test_read_battle_enter_packet(self):
        path = SESSION_DIR / "s2c_0x4013_1599_212333.620.bin"
        if not path.exists():
            pytest.skip("battle_enter packet not found")
        pkt = read_bin_packet(path)
        assert pkt["cmd"] == 0x4013
        assert pkt["seq"] == 1599
        assert pkt["direction"] == "s2c"
        assert len(pkt["decrypted_body_hex"]) > 0

    def test_parse_record_returns_1316(self):
        path = SESSION_DIR / "s2c_0x4013_1599_212333.620.bin"
        if not path.exists():
            pytest.skip("battle_enter packet not found")
        pkt = read_bin_packet(path)
        record = parse_record(pkt)
        assert record is not None
        assert record["opcode"] == 0x1316


# ---------------------------------------------------------------------------
# TestBattlePipeline — verify each parsing stage
# ---------------------------------------------------------------------------


class TestBattlePipeline:
    def test_all_packets_parseable(self, session1_packets):
        assert len(session1_packets) > 0, "No battle packets found"
        for item in session1_packets:
            assert item["record"] is not None, f"parse_record returned None for {item['filename']}"

    def test_all_packets_have_known_opcodes(self, session1_packets):
        unknown = [item for item in session1_packets if item["opcode"] not in BATTLE_OPCODES]
        assert not unknown, f"Unexpected opcodes: {[(i['filename'], hex(i['opcode'])) for i in unknown]}"

    def test_summarize_not_unknown(self, session1_packets):
        unknown = []
        for item in session1_packets:
            record = item["record"]
            inner = None
            if record.get("opcode") == 0x0414:
                inner = extract_inner_message(record.get("root", {}))
            kind, _ = summarize(record, inner)
            if kind == "unknown":
                unknown.append((item["filename"], hex(item["opcode"])))
        assert not unknown, f"Unknown opcodes in summarize: {unknown}"

    def test_battle_enter_present(self, session1_packets):
        enter = [p for p in session1_packets if p["opcode"] == 0x1316]
        assert len(enter) == 1, f"Expected 1 battle_enter, got {len(enter)}"

    def test_battle_finish_present(self, session1_packets):
        finish = [p for p in session1_packets if p["opcode"] == 0x132C]
        assert len(finish) == 1, f"Expected 1 battle_finish, got {len(finish)}"


# ---------------------------------------------------------------------------
# TestWrapperExtraction — verify state wrappers have required fields
# ---------------------------------------------------------------------------


class TestWrapperExtraction:
    def test_1316_wrappers_have_pets(self, session1_packets):
        enter = next(p for p in session1_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter["record"])
        assert len(wrappers) >= 2, f"Expected >= 2 wrappers, got {len(wrappers)}"

    def test_wrappers_have_side(self, session1_packets):
        enter = next(p for p in session1_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter["record"])
        for w in wrappers:
            assert "side" in w and w["side"] is not None, (
                f"Wrapper missing 'side' field: pet={w.get('name')} slot={w.get('slot')}"
            )

    def test_wrappers_have_pet_names(self, session1_packets):
        enter = next(p for p in session1_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter["record"])
        for w in wrappers:
            assert w.get("name"), f"Wrapper missing name: {w}"

    def test_wrappers_have_hp(self, session1_packets):
        enter = next(p for p in session1_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter["record"])
        for w in wrappers:
            assert w.get("max_hp") is not None or w.get("battle_max_hp") is not None, (
                f"Wrapper missing max_hp: pet={w.get('name')}"
            )

    def test_both_sides_present(self, session1_packets):
        enter = next(p for p in session1_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter["record"])
        sides = set(w.get("side") for w in wrappers)
        assert 1 in sides, f"No 我方(side=1) pets found, sides={sides}"
        assert 401 in sides, f"No 敌方(side=401) pets found, sides={sides}"


# ---------------------------------------------------------------------------
# TestBattleStateReplay — full replay through BattleStateTracker
# ---------------------------------------------------------------------------


class TestBattleStateReplay:
    def test_my_pets_populated(self, session1_baseline_result):
        _, state = session1_baseline_result
        assert len(state["my_pets"]) > 0, "my_pets is empty after battle replay"

    def test_opp_pets_populated(self, session1_baseline_result):
        _, state = session1_baseline_result
        assert len(state["opp_pets"]) > 0, "opp_pets is empty after battle replay"

    def test_battle_id_set(self, session1_baseline_result):
        _, state = session1_baseline_result
        assert state["battle_id"] is not None, "battle_id not set"

    def test_battle_result(self, session1_baseline_result):
        _, state = session1_baseline_result
        assert state["result"] in ("WIN", "LOSE", "RUNAWAY", "WIN_DEFEAT", "MONSTER_RUNAWAY", "WIN_HP", "WIN_CATCH", "RUNAWAY_ROLE_MAGIC"), (
            f"Unexpected result: {state['result']}"
        )

    def test_rounds_tracked(self, session1_baseline_result):
        events, state = session1_baseline_result
        round_events = [e for e in events if e["opcode"] == 0x131A]
        assert len(round_events) > 0, "No round_start events processed"
        assert state["round"] > 0, "Round not incremented"

    def test_events_collected(self, session1_baseline_result):
        _, state = session1_baseline_result
        assert len(state["events"]) >= 10, f"Too few events: {len(state['events'])}"

    def test_my_active_set(self, session1_baseline_result):
        _, state = session1_baseline_result
        assert state["my_active"] is not None, "my_active not set"

    def test_opp_active_set(self, session1_baseline_result):
        _, state = session1_baseline_result
        assert state["opp_active"] is not None, "opp_active not set"

    def test_hp_changes_tracked(self, session1_baseline_result):
        events, state = session1_baseline_result
        damage_events = [
            e for e in events
            if e["opcode"] == 0x1324
            and isinstance(e.get("detail"), dict)
            and e["detail"].get("entries")
        ]
        assert len(damage_events) > 0, "No damage events found in replay"

    def test_all_six_opponent_pets_tracked(self, session1_baseline_result):
        _, state = session1_baseline_result
        assert len(state["opp_pets"]) == 6, (
            f"Expected 6 opponent pets, got {len(state['opp_pets'])}: "
            f"{[p['name'] for p in state['opp_pets']]}"
        )

    def test_opponent_pets_have_known_names(self, session1_baseline_result):
        _, state = session1_baseline_result
        expected = {"白发路路", "火神", "翼龙", "利灯鱼", "咔咔鸟"}
        opp_names = {p["name"] for p in state["opp_pets"]}
        missing = expected - opp_names
        assert not missing, f"Missing opponent pets: {missing}, got: {opp_names}"

    def test_opponent_pets_have_valid_hp(self, session1_baseline_result):
        _, state = session1_baseline_result
        for p in state["opp_pets"]:
            assert p["max_hp"] > 0, f"Opponent pet {p['name']} has no max_hp"
            assert p["current_hp"] >= 0, f"Opponent pet {p['name']} has negative hp"
            assert p["current_hp"] <= p["max_hp"], (
                f"Opponent pet {p['name']} hp={p['current_hp']} > max_hp={p['max_hp']}"
            )

    def test_player_pets_have_valid_hp(self, session1_baseline_result):
        _, state = session1_baseline_result
        for p in state["my_pets"]:
            assert p["max_hp"] > 0, f"Player pet {p['name']} has no max_hp"
            assert p["current_hp"] >= 0, f"Player pet {p['name']} has negative hp"
            assert p["current_hp"] <= p["max_hp"], (
                f"Player pet {p['name']} hp={p['current_hp']} > max_hp={p['max_hp']}"
            )

    def test_round_start_wrappers_have_side(self, session1_packets):
        from src.protocol.proto_core import extract_state_wrappers_from_record
        rs = [p for p in session1_packets if p["opcode"] == 0x131A]
        assert len(rs) > 0, "No round_start packets"
        for item in rs:
            wrappers = extract_state_wrappers_from_record(item["record"])
            for w in wrappers:
                assert w.get("side") in (1, 401), (
                    f"Round-start wrapper has invalid side={w.get('side')}: "
                    f"name={w.get('name')} path={w.get('path')}"
                )


# ---------------------------------------------------------------------------
# TestEventFormatterReplay — replay through EventFormatter with real data
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def formatted_replay(session1_baseline_result):
    """Replay all events through EventFormatter, return (formatted_events, state)."""
    events, state = session1_baseline_result
    all_formatted = []
    for e in events:
        opcode = e["opcode"]
        detail = e["detail"]
        current_state = e["state"]
        round_num = current_state.get("round", 0)
        formatted = format_battle_event(opcode, detail, current_state, round_num)
        all_formatted.extend(formatted)
    return all_formatted, state


class TestEventFormatterReplay:
    def test_all_packets_format_without_error(self, formatted_replay):
        formatted, _ = formatted_replay
        assert len(formatted) > 0, "No formatted events produced"

    def test_no_empty_summaries(self, formatted_replay):
        formatted, _ = formatted_replay
        empty = [fe for fe in formatted if not fe.summary.strip()]
        assert not empty, f"{len(empty)} events have empty summaries"

    def test_battle_enter_event(self, formatted_replay):
        formatted, _ = formatted_replay
        enter_events = [fe for fe in formatted if fe.kind == "battle_enter"]
        assert len(enter_events) == 1
        ev = enter_events[0]
        assert "battle_id" in ev.detail
        assert ev.detail["my_team"] or ev.detail["opp_team"]
        assert ev.color == "green"

    def test_battle_finish_event(self, formatted_replay):
        formatted, state = formatted_replay
        finish_events = [fe for fe in formatted if fe.kind == "battle_finish"]
        assert len(finish_events) == 1
        ev = finish_events[0]
        assert ev.detail["result"] is not None
        assert ev.round == state["round"]

    def test_damage_events_have_values(self, formatted_replay):
        formatted, _ = formatted_replay
        damage_events = [fe for fe in formatted if fe.kind == "damage"]
        assert len(damage_events) > 0, "No damage events in battle"
        for ev in damage_events:
            assert isinstance(ev.detail["damage"], int)
            assert ev.detail["damage"] > 0, f"Damage event has 0 damage: {ev.summary}"

    def test_skill_cast_events(self, formatted_replay):
        formatted, _ = formatted_replay
        skill_events = [fe for fe in formatted if fe.kind == "skill_cast"]
        assert len(skill_events) > 0, "No skill_cast events in battle"

    def test_defeat_events(self, formatted_replay):
        formatted, _ = formatted_replay
        defeat_events = [fe for fe in formatted if fe.kind == "defeat"]
        assert len(defeat_events) > 0, "No defeat events in battle"
        for ev in defeat_events:
            assert "我方" in ev.summary or "敌方" in ev.summary

    def test_change_pet_events(self, formatted_replay):
        formatted, _ = formatted_replay
        change_events = [fe for fe in formatted if fe.kind == "change_pet"]
        assert len(change_events) > 0, "No change_pet events in battle"
        for ev in change_events:
            assert "→" in ev.summary, f"change_pet missing arrow: {ev.summary}"
            assert "我方" in ev.summary or "敌方" in ev.summary

    def test_round_start_events(self, formatted_replay):
        formatted, _ = formatted_replay
        round_events = [fe for fe in formatted if fe.kind == "round_start"]
        assert len(round_events) > 0, "No round_start events"
        rounds_seen = {ev.round for ev in round_events}
        assert len(rounds_seen) > 1, f"Only {len(rounds_seen)} distinct rounds"

    def test_effect_events_present(self, formatted_replay):
        formatted, _ = formatted_replay
        effect_kinds = {"effect_apply", "effect_stage", "effect_link", "effect_trigger"}
        effect_events = [fe for fe in formatted if fe.kind in effect_kinds]
        assert len(effect_events) > 0, "No effect events in battle"

    def test_all_kinds_have_valid_color(self, formatted_replay):
        formatted, _ = formatted_replay
        valid_colors = {"green", "red", "blue", "gold", "gray", "purple", "cyan", "geekblue"}
        bad = [fe for fe in formatted if fe.color not in valid_colors]
        assert not bad, f"Invalid colors: {set(fe.color for fe in bad)}"

    def test_event_kinds_distribution(self, formatted_replay):
        formatted, _ = formatted_replay
        kinds = {fe.kind for fe in formatted}
        expected_kinds = {
            "battle_enter", "round_start", "skill_cast", "damage",
            "battle_finish", "skill_select", "skill_declare",
        }
        missing = expected_kinds - kinds
        assert not missing, f"Missing expected event kinds: {missing}"


class TestBattleSummaryReplay:
    def test_summary_computed(self, session1_baseline_result):
        _, state = session1_baseline_result
        summary = compute_battle_summary(state)
        assert summary["result"] is not None
        assert summary["rounds"] > 0

    def test_summary_pet_counts(self, session1_baseline_result):
        _, state = session1_baseline_result
        summary = compute_battle_summary(state)
        assert len(summary["my_pets_final"]) == len(state["my_pets"])
        assert len(summary["opp_pets_final"]) == len(state["opp_pets"])

    def test_summary_final_hp_valid(self, session1_baseline_result):
        _, state = session1_baseline_result
        summary = compute_battle_summary(state)
        for p in summary["my_pets_final"] + summary["opp_pets_final"]:
            assert p["hp"] >= 0
            assert p["max_hp"] > 0
            assert p["status"] in ("存活", "战败")

    def test_summary_event_stats(self, session1_baseline_result):
        _, state = session1_baseline_result
        summary = compute_battle_summary(state)
        assert len(summary["event_stats"]) > 0
        total = sum(summary["event_stats"].values())
        assert total == len(state["events"])
