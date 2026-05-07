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
from tests.packet_reader import (
    read_bin_packet,
    load_battle_packets,
    replay_battle,
    BATTLE_OPCODES,
)

SESSION_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"


@pytest.fixture(scope="module")
def battle_packets():
    return load_battle_packets(SESSION_DIR)


@pytest.fixture(scope="module")
def replay_result(battle_packets):
    return replay_battle(battle_packets)


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
    def test_all_packets_parseable(self, battle_packets):
        assert len(battle_packets) > 0, "No battle packets found"
        for item in battle_packets:
            assert item["record"] is not None, f"parse_record returned None for {item['filename']}"

    def test_all_packets_have_known_opcodes(self, battle_packets):
        unknown = [item for item in battle_packets if item["opcode"] not in BATTLE_OPCODES]
        assert not unknown, f"Unexpected opcodes: {[(i['filename'], hex(i['opcode'])) for i in unknown]}"

    def test_summarize_not_unknown(self, battle_packets):
        unknown = []
        for item in battle_packets:
            record = item["record"]
            inner = None
            if record.get("opcode") == 0x0414:
                inner = extract_inner_message(record.get("root", {}))
            kind, _ = summarize(record, inner)
            if kind == "unknown":
                unknown.append((item["filename"], hex(item["opcode"])))
        assert not unknown, f"Unknown opcodes in summarize: {unknown}"

    def test_battle_enter_present(self, battle_packets):
        enter = [p for p in battle_packets if p["opcode"] == 0x1316]
        assert len(enter) == 1, f"Expected 1 battle_enter, got {len(enter)}"

    def test_battle_finish_present(self, battle_packets):
        finish = [p for p in battle_packets if p["opcode"] == 0x132C]
        assert len(finish) == 1, f"Expected 1 battle_finish, got {len(finish)}"


# ---------------------------------------------------------------------------
# TestWrapperExtraction — verify state wrappers have required fields
# ---------------------------------------------------------------------------


class TestWrapperExtraction:
    def test_1316_wrappers_have_pets(self, battle_packets):
        enter = next(p for p in battle_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter["record"])
        assert len(wrappers) >= 2, f"Expected >= 2 wrappers, got {len(wrappers)}"

    def test_wrappers_have_side(self, battle_packets):
        enter = next(p for p in battle_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter["record"])
        for w in wrappers:
            assert "side" in w and w["side"] is not None, (
                f"Wrapper missing 'side' field: pet={w.get('name')} slot={w.get('slot')}"
            )

    def test_wrappers_have_pet_names(self, battle_packets):
        enter = next(p for p in battle_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter["record"])
        for w in wrappers:
            assert w.get("name"), f"Wrapper missing name: {w}"

    def test_wrappers_have_hp(self, battle_packets):
        enter = next(p for p in battle_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter["record"])
        for w in wrappers:
            assert w.get("max_hp") is not None or w.get("battle_max_hp") is not None, (
                f"Wrapper missing max_hp: pet={w.get('name')}"
            )

    def test_both_sides_present(self, battle_packets):
        enter = next(p for p in battle_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter["record"])
        sides = set(w.get("side") for w in wrappers)
        assert 1 in sides, f"No 我方(side=1) pets found, sides={sides}"
        assert 401 in sides, f"No 敌方(side=401) pets found, sides={sides}"


# ---------------------------------------------------------------------------
# TestBattleStateReplay — full replay through BattleStateTracker
# ---------------------------------------------------------------------------


class TestBattleStateReplay:
    def test_my_pets_populated(self, replay_result):
        _, state = replay_result
        assert len(state["my_pets"]) > 0, "my_pets is empty after battle replay"

    def test_opp_pets_populated(self, replay_result):
        _, state = replay_result
        assert len(state["opp_pets"]) > 0, "opp_pets is empty after battle replay"

    def test_battle_id_set(self, replay_result):
        _, state = replay_result
        assert state["battle_id"] is not None, "battle_id not set"

    def test_battle_result(self, replay_result):
        _, state = replay_result
        assert state["result"] in ("WIN", "LOSE", "RUNAWAY", "WIN_DEFEAT", "MONSTER_RUNAWAY", "WIN_HP", "WIN_CATCH", "RUNAWAY_ROLE_MAGIC"), (
            f"Unexpected result: {state['result']}"
        )

    def test_rounds_tracked(self, replay_result):
        events, state = replay_result
        round_events = [e for e in events if e["opcode"] == 0x131A]
        assert len(round_events) > 0, "No round_start events processed"
        assert state["round"] > 0, "Round not incremented"

    def test_events_collected(self, replay_result):
        _, state = replay_result
        assert len(state["events"]) >= 10, f"Too few events: {len(state['events'])}"

    def test_my_active_set(self, replay_result):
        _, state = replay_result
        assert state["my_active"] is not None, "my_active not set"

    def test_opp_active_set(self, replay_result):
        _, state = replay_result
        assert state["opp_active"] is not None, "opp_active not set"

    def test_hp_changes_tracked(self, replay_result):
        events, state = replay_result
        damage_events = [
            e for e in events
            if e["opcode"] == 0x1324
            and isinstance(e.get("detail"), dict)
            and e["detail"].get("entries")
        ]
        assert len(damage_events) > 0, "No damage events found in replay"

    def test_all_six_opponent_pets_tracked(self, replay_result):
        _, state = replay_result
        assert len(state["opp_pets"]) == 6, (
            f"Expected 6 opponent pets, got {len(state['opp_pets'])}: "
            f"{[p['name'] for p in state['opp_pets']]}"
        )

    def test_opponent_pets_have_known_names(self, replay_result):
        _, state = replay_result
        expected = {"白发路路", "火神", "翼龙", "利灯鱼", "咔咔鸟"}
        opp_names = {p["name"] for p in state["opp_pets"]}
        missing = expected - opp_names
        assert not missing, f"Missing opponent pets: {missing}, got: {opp_names}"

    def test_opponent_pets_have_valid_hp(self, replay_result):
        _, state = replay_result
        for p in state["opp_pets"]:
            assert p["max_hp"] > 0, f"Opponent pet {p['name']} has no max_hp"
            assert p["current_hp"] >= 0, f"Opponent pet {p['name']} has negative hp"
            assert p["current_hp"] <= p["max_hp"], (
                f"Opponent pet {p['name']} hp={p['current_hp']} > max_hp={p['max_hp']}"
            )

    def test_player_pets_have_valid_hp(self, replay_result):
        _, state = replay_result
        for p in state["my_pets"]:
            assert p["max_hp"] > 0, f"Player pet {p['name']} has no max_hp"
            assert p["current_hp"] >= 0, f"Player pet {p['name']} has negative hp"
            assert p["current_hp"] <= p["max_hp"], (
                f"Player pet {p['name']} hp={p['current_hp']} > max_hp={p['max_hp']}"
            )

    def test_round_start_wrappers_have_side(self, battle_packets):
        from src.protocol.proto_core import extract_state_wrappers_from_record
        rs = [p for p in battle_packets if p["opcode"] == 0x131A]
        assert len(rs) > 0, "No round_start packets"
        for item in rs:
            wrappers = extract_state_wrappers_from_record(item["record"])
            for w in wrappers:
                assert w.get("side") in (1, 401), (
                    f"Round-start wrapper has invalid side={w.get('side')}: "
                    f"name={w.get('name')} path={w.get('path')}"
                )
