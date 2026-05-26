"""Shared test fixtures — session-scoped to avoid redundant I/O."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.packet_reader import load_battle_packets, replay_battle
from src.analysis.replay_runner import BattleReplayRunner

SESSION1_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"
SESSION2_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_2"
SESSION3_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_3"
SESSION8_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_8"
SESSION9_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_9"


@pytest.fixture(scope="session")
def session1_packets():
    """Load battle_session_1 packets once for the entire test session."""
    if not SESSION1_DIR.exists():
        pytest.skip("battle_session_1 fixtures not found")
    return load_battle_packets(SESSION1_DIR)


@pytest.fixture(scope="session")
def session1_baseline_result(session1_packets):
    """Replay battle_session_1 through BattleStateTracker once."""
    return replay_battle(session1_packets)


@pytest.fixture(scope="session")
def session1_runner_result(session1_packets):
    """Replay battle_session_1 through BattleReplayRunner once."""
    runner = BattleReplayRunner()
    return runner.run(session1_packets)


@pytest.fixture(scope="session")
def session3_packets():
    """Load battle_session_3 packets once for the entire test session."""
    if not SESSION3_DIR.exists():
        pytest.skip("battle_session_3 fixtures not found")
    return load_battle_packets(SESSION3_DIR)


@pytest.fixture(scope="session")
def session3_runner_result(session3_packets):
    """Replay battle_session_3 through BattleReplayRunner once."""
    runner = BattleReplayRunner()
    return runner.run(session3_packets)


@pytest.fixture(scope="session")
def session8_packets():
    """Load battle_session_8 packets once for the entire test session."""
    if not SESSION8_DIR.exists():
        pytest.skip("battle_session_8 fixtures not found")
    return load_battle_packets(SESSION8_DIR)


@pytest.fixture(scope="session")
def session8_runner_result(session8_packets):
    """Replay battle_session_8 through BattleReplayRunner once."""
    runner = BattleReplayRunner()
    return runner.run(session8_packets)


@pytest.fixture(scope="session")
def session9_packets():
    """Load battle_session_9 packets once for the entire test session."""
    if not SESSION9_DIR.exists():
        pytest.skip("battle_session_9 fixtures not found")
    return load_battle_packets(SESSION9_DIR)


@pytest.fixture(scope="session")
def session9_runner_result(session9_packets):
    """Replay battle_session_9 through BattleReplayRunner once."""
    runner = BattleReplayRunner()
    return runner.run(session9_packets)
