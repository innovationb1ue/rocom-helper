"""DamageCalculator phase mixin tests."""
from __future__ import annotations

from src.analysis.damage.calculator_phases import DamageCalculationPhasesMixin
from src.game.type_chart import TypeChart


class PhaseHarness(DamageCalculationPhasesMixin):
    def __init__(self) -> None:
        self.chart = TypeChart()
        self._server_power_rules = {}
        self.hook_calls = []

    def _run_hooks(self, stage, ctx):
        self.hook_calls.append(stage)
        if stage == "pre_power":
            return {**ctx, "power": ctx["power"] + 5}
        if stage == "post_base":
            return {**ctx, "base_damage": ctx["base_damage"] * 2}
        return ctx


def test_phase_mixin_resolves_power_through_pre_power_hooks():
    harness = PhaseHarness()

    power, ctx = harness._resolve_power(80, {"id": 1}, {"name": "我方"}, {"name": "敌方"})

    assert power == 85
    assert ctx["power"] == 85
    assert harness.hook_calls == ["pre_power"]


def test_phase_mixin_computes_base_damage_through_post_base_hooks():
    harness = PhaseHarness()

    base = harness._compute_base_damage(
        80,
        200.0,
        100.0,
        {"id": 1},
        {"name": "我方"},
        {"name": "敌方"},
    )

    assert base == 288.0
    assert harness.hook_calls == ["post_base"]


def test_phase_mixin_apply_multipliers_uses_chart_and_hooks():
    harness = PhaseHarness()

    result = harness._apply_multipliers(
        100.0,
        1,
        {"types": [1]},
        {"types": [0]},
        {"id": 1},
        weather=None,
    )

    damage, effectiveness, stab, weather_mult, power_mult, label, is_stab = result
    assert damage > 0
    assert effectiveness > 0
    assert stab == 1.5
    assert weather_mult == 1.0
    assert power_mult == 1.0
    assert label
    assert is_stab is True
