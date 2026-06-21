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
SESSION10_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_10"
SESSION11_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_11"
SESSION12_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_12"
SESSION13_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_13"


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
def session1_state_only_result(session1_packets):
    """Replay battle_session_1 without analysis/hooks once."""
    return BattleReplayRunner(include_analysis=False, include_hooks=False).run(session1_packets)


@pytest.fixture(scope="session")
def session1_round8_state(session1_state_only_result):
    """Expose the round 8 end state from the shared state-only replay."""
    return next(
        round_snapshot.state_at_end
        for round_snapshot in session1_state_only_result.rounds
        if round_snapshot.round_num == 8
    )


@pytest.fixture(scope="session")
def session2_packets():
    """Load battle_session_2 packets once for the entire test session."""
    if not SESSION2_DIR.exists():
        pytest.skip("battle_session_2 fixtures not found")
    return load_battle_packets(SESSION2_DIR)


@pytest.fixture(scope="session")
def session2_runner_result(session2_packets):
    """Replay battle_session_2 through BattleReplayRunner once."""
    runner = BattleReplayRunner()
    return runner.run(session2_packets)


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


@pytest.fixture(scope="session")
def session10_packets():
    """Load battle_session_10 packets once for the entire test session."""
    if not SESSION10_DIR.exists():
        pytest.skip("battle_session_10 fixtures not found")
    return load_battle_packets(SESSION10_DIR)


@pytest.fixture(scope="session")
def session10_runner_result(session10_packets):
    """Replay battle_session_10 through BattleReplayRunner once."""
    runner = BattleReplayRunner()
    return runner.run(session10_packets)


@pytest.fixture(scope="session")
def session11_packets():
    """Load battle_session_11 packets once for the entire test session."""
    if not SESSION11_DIR.exists():
        pytest.skip("battle_session_11 fixtures not found")
    return load_battle_packets(SESSION11_DIR)


@pytest.fixture(scope="session")
def session11_runner_result(session11_packets):
    """Replay battle_session_11 through BattleReplayRunner once."""
    runner = BattleReplayRunner()
    return runner.run(session11_packets)


@pytest.fixture(scope="session")
def session12_packets():
    """Load battle_session_12 packets once for the entire test session."""
    if not SESSION12_DIR.exists():
        pytest.skip("battle_session_12 fixtures not found")
    return load_battle_packets(SESSION12_DIR)


@pytest.fixture(scope="session")
def session12_runner_result(session12_packets):
    """Replay battle_session_12 through BattleReplayRunner once."""
    runner = BattleReplayRunner()
    return runner.run(session12_packets)


@pytest.fixture(scope="session")
def session13_packets():
    """Load battle_session_13 packets once for the entire test session."""
    if not SESSION13_DIR.exists():
        pytest.skip("battle_session_13 fixtures not found")
    return load_battle_packets(SESSION13_DIR)


@pytest.fixture(scope="session")
def session13_runner_result(session13_packets):
    """Replay battle_session_13 through BattleReplayRunner once."""
    runner = BattleReplayRunner()
    return runner.run(session13_packets)
