"""State-level suggestion guardrail tests."""
from __future__ import annotations

from src.analysis.suggestions import build_state_suggestions


def _state(**overrides):
    state = {
        "phase": "resolving",
        "result": None,
        "terminal_pending": False,
        "my_active": {"current_hp": 100, "hp_pct": 1.0, "energy": 5, "buffs": []},
        "opp_active": {"current_hp": 10, "hp_pct": 0.05, "energy": 5, "buffs": []},
    }
    state.update(overrides)
    return state


def test_build_state_suggestions_keeps_normal_finish_off_during_active_battle():
    suggestions = build_state_suggestions(_state())

    assert {"type": "finish_off", "message": "对手精灵HP极低，可尝试击杀"} in suggestions


def test_build_state_suggestions_suppressed_when_finished_or_settling():
    assert build_state_suggestions(_state(phase="finished", result="WIN_HP")) == []
    assert build_state_suggestions(_state(phase="settling", terminal_pending=True)) == []


def test_build_state_suggestions_suppressed_when_active_pet_is_defeated():
    assert build_state_suggestions(_state(opp_active={"current_hp": 0, "hp_pct": 0.0})) == []
