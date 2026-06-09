"""战术 hook 信号评分修饰测试。"""
from __future__ import annotations

from src.analysis.tactical import hook_signal_scoring


def test_prefer_switch_boosts_switch_actions_only():
    switch = {"action_type": "switch"}
    skill = {"action_type": "skill", "energy_cost": 0}
    signals = [{"signal_type": "prefer_switch"}]

    assert hook_signal_scoring.apply_hook_signal_modifiers(1.0, switch, signals) == 1.2
    assert hook_signal_scoring.apply_hook_signal_modifiers(1.0, skill, signals) == 1.0


def test_avoid_skill_scales_by_energy_cost():
    assert hook_signal_scoring.apply_hook_signal_modifiers(
        1.0,
        {"action_type": "skill", "energy_cost": 5},
        [{"signal_type": "avoid_skill"}],
    ) == 0.5
    assert hook_signal_scoring.apply_hook_signal_modifiers(
        1.0,
        {"action_type": "skill", "energy_cost": 1},
        [{"signal_type": "avoid_skill"}],
    ) == 0.8
    assert hook_signal_scoring.apply_hook_signal_modifiers(
        1.0,
        {"action_type": "skill", "energy_cost": 0},
        [{"signal_type": "avoid_skill"}],
    ) == 1.0


def test_unknown_signals_are_ignored():
    assert hook_signal_scoring.apply_hook_signal_modifiers(
        1.0,
        {"action_type": "switch"},
        [{"signal_type": "unknown"}],
    ) == 1.0
