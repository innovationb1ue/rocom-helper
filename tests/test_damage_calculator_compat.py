"""DamageCalculator legacy helper mixin tests."""
from __future__ import annotations

from src.analysis.damage.calculator_compat import DamageCalculatorCompatMixin


def test_compat_mixin_keeps_formula_and_skill_helpers():
    assert DamageCalculatorCompatMixin._base_damage(200, 100, 80) == 144.0
    assert DamageCalculatorCompatMixin._get_power({"dam_para": [90]}) == 90
    assert DamageCalculatorCompatMixin._get_base_hit_count({"desc": "造成物伤，3连击。"}) == 3


def test_compat_mixin_keeps_runtime_and_stat_helpers():
    runtime = {"1001": {"cost_energy_result": 3}}
    attacker = {"skill_runtime": runtime}

    assert DamageCalculatorCompatMixin._get_runtime_skill(attacker, 1001) == runtime["1001"]
    assert DamageCalculatorCompatMixin._resolve_energy_cost(
        runtime["1001"],
        {"energy_cost": [5]},
    ) == (3, "skill_sync.cost_energy_result")
    assert DamageCalculatorCompatMixin._get_stat({"stats": [{"name": "ATK", "total": 250}]}, "ATK") == 250


def test_compat_mixin_resolves_server_runtime_by_target_keys():
    mixin = DamageCalculatorCompatMixin()
    runtime_skill = {"damage_params_by_pet": {"401": 80}}
    defender = {"slot": 401}

    resolved = mixin._resolve_server_runtime(runtime_skill, defender)

    assert resolved["power"] == 80
    assert resolved["power_source"] == "server_damage_params"
    assert resolved["matched_target_key"] == "401"
