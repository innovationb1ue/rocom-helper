from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from src.analysis.battle_report import build_report_analysis as facade_build_report_analysis
from src.analysis.reporting.analysis import build_report_analysis, compact_messages
from src.analysis.reporting.window import load_battle_packets_for_window, scan_battles

FIXTURE_SESSION = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"


@pytest.fixture()
def report_packets(tmp_path: Path):
    if not FIXTURE_SESSION.exists():
        pytest.skip("battle_session_1 fixture not found")
    session_dir = tmp_path / "2026-05-07_21-17-31_monitor"
    shutil.copytree(FIXTURE_SESSION, session_dir)
    boundary = scan_battles(session_dir)[0]
    return load_battle_packets_for_window(session_dir, boundary)


def test_report_analysis_is_compact_and_matches_facade(report_packets):
    direct = build_report_analysis(report_packets, include_events=False)
    through_facade = facade_build_report_analysis(report_packets, include_events=False)

    assert direct == through_facade
    assert direct["total_packets"] == len(report_packets)
    assert direct["events"] == []
    assert direct["final_state"]["round"] == 17
    assert direct["battle_summary"]["result"] == "WIN_HP"
    assert direct["messages"]
    assert all("state_before" not in message for message in direct["messages"])
    assert all("state_after" not in message for message in direct["messages"])


def test_report_analysis_can_include_lightweight_events(report_packets):
    analysis = build_report_analysis(report_packets, include_events=True)

    assert analysis["events"]
    sample = analysis["events"][0]
    assert {"index", "opcode", "kind", "round_num", "filename", "messages"}.issubset(sample)
    assert "state_before" not in sample
    assert "state_after" not in sample


def test_compact_messages_emit_browser_compatible_minimum_payloads():
    messages = compact_messages(
        0x132C,
        {
            "round": 3,
            "phase": "finished",
            "result": "WIN_HP",
            "my_active": {"pet_id": 1, "name": "我方", "current_hp": 10, "max_hp": 100},
            "opp_active": {"pet_id": 2, "name": "敌方", "current_hp": 0, "max_hp": 100},
        },
        [{"kind": "battle_finish", "summary": "战斗结束"}],
        [{"type": "info", "message": "已结束"}],
    )

    assert [message["type"] for message in messages] == [
        "battle_event",
        "state_update",
        "suggestions",
        "battle_summary",
    ]
    assert messages[1]["my_active"]["name"] == "我方"
    assert messages[1]["opp_active"]["current_hp"] == 0
