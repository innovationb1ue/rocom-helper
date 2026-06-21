"""DamageCalculator runtime configuration helper tests."""
from __future__ import annotations

from src.analysis.damage.calculator_config import normalize_server_power_rules


def test_normalize_server_power_rules_accepts_nested_skills_mapping():
    rules = {
        "skills": {
            7700001: {"enabled": True, "mode": "multiplier_over_base_power"},
            "bad": "not-a-rule",
        }
    }

    result = normalize_server_power_rules(rules)

    assert result == {
        "7700001": {"enabled": True, "mode": "multiplier_over_base_power"}
    }


def test_normalize_server_power_rules_accepts_direct_legacy_mapping_and_copies_rules():
    rule = {"enabled": True}
    result = normalize_server_power_rules({7700001: rule})

    assert result == {"7700001": {"enabled": True}}
    assert result["7700001"] is not rule


def test_normalize_server_power_rules_ignores_invalid_shapes():
    assert normalize_server_power_rules({"skills": []}) == {}
    assert normalize_server_power_rules([]) == {}
