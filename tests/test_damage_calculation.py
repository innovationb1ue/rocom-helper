"""Single-skill damage calculation orchestration tests."""
from __future__ import annotations

from src.analysis.damage.calculation import calculate_damage


class FakeCalculator:
    def __init__(self, *, power: int = 80, stats=None) -> None:
        self.power = power
        self.stats = stats or (200.0, 100.0, 1.0, "high", [], {"attack": "total", "defense": "total"})
        self.calls = []
        self.server_runtime = {"runtime": True}

    def _get_power(self, skill_meta):
        self.calls.append("_get_power")
        return self.power

    def _get_runtime_skill(self, attacker, skill_id):
        self.calls.append(("_get_runtime_skill", skill_id))
        return {"skill_id": skill_id}

    def _resolve_server_runtime(self, runtime_skill, defender):
        self.calls.append(("_resolve_server_runtime", runtime_skill, defender))
        return self.server_runtime

    def _apply_server_power_rule(self, server_runtime, skill_meta, base_power):
        self.calls.append(("_apply_server_power_rule", base_power))
        server_runtime["rule_checked"] = True

    def _resolve_power(self, power, skill_meta, attacker, defender):
        self.calls.append(("_resolve_power", power))
        return power + 5, {}

    def _resolve_combat_stats(self, attacker, defender, damage_type, power):
        self.calls.append(("_resolve_combat_stats", damage_type, power))
        return self.stats

    def _compute_base_damage(self, power, effective_atk, effective_def, skill_meta, attacker, defender):
        self.calls.append(("_compute_base_damage", power, effective_atk, effective_def))
        return 180.0

    def _apply_multipliers(self, base, skill_element, attacker, defender, skill_meta, weather, server_runtime):
        self.calls.append(("_apply_multipliers", base, skill_element, weather, server_runtime))
        return (270, 2.0, 1.5, 1.0, 1.0, "效果拔群", True)

    def _finalize_damage(
        self,
        dmg,
        power,
        ability_level,
        effective_atk,
        effective_def,
        effectiveness,
        stab_mult,
        weather_mult,
        power_mult,
        skill_meta,
        skill_element,
        attacker,
        defender,
        damage_type,
        eff_label,
        is_stab,
        confidence,
        warnings,
        stat_sources,
        runtime_skill,
        server_runtime,
        final_power,
    ):
        self.calls.append(("_finalize_damage", dmg, power, final_power, runtime_skill, server_runtime))
        return {
            "damage": dmg,
            "power": power,
            "final_power": final_power,
            "damage_type": damage_type,
            "skill_element": skill_element,
        }


def test_calculate_damage_runs_stages_and_marks_server_runtime():
    calc = FakeCalculator()
    skill = {
        "id": 7700001,
        "name": "火焰冲击",
        "damage_type": 2,
        "skill_dam_type": 1,
    }
    weather = {"id": 5}

    result = calculate_damage(calc, {"buffs": []}, {"types": [3]}, skill, weather=weather)

    assert result == {
        "damage": 270,
        "power": 85,
        "final_power": 85,
        "damage_type": 2,
        "skill_element": 1,
    }
    assert calc.server_runtime["formula_power_source"] == "skill_config"
    assert calc.server_runtime["power_used_in_formula"] is False
    assert calc.server_runtime["rule_checked"] is True
    assert calc.calls[-1][0] == "_finalize_damage"


def test_calculate_damage_skips_non_attack_after_server_runtime_explanation():
    calc = FakeCalculator(power=0)
    skill = {"id": 7700001, "damage_type": 0, "skill_dam_type": 1}

    assert calculate_damage(calc, {"buffs": []}, {}, skill) is None

    assert calc.server_runtime["formula_power_source"] == "skill_config"
    assert calc.server_runtime["power_used_in_formula"] is False
    assert ("_apply_server_power_rule", 0) in calc.calls
    assert not any(call[0] == "_resolve_power" for call in calc.calls if isinstance(call, tuple))


def test_calculate_damage_returns_none_when_stats_unavailable():
    calc = FakeCalculator(stats=None)
    calc.stats = None
    skill = {"id": 7700001, "damage_type": 2, "skill_dam_type": 1}

    assert calculate_damage(calc, {"buffs": []}, {}, skill) is None

    assert any(call[0] == "_resolve_combat_stats" for call in calc.calls if isinstance(call, tuple))
    assert not any(call[0] == "_compute_base_damage" for call in calc.calls if isinstance(call, tuple))
