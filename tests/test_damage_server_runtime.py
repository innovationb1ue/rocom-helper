"""服务端同步伤害 runtime 解析测试。"""
from __future__ import annotations

from src.analysis.damage.server_runtime import apply_server_power_rule, resolve_server_runtime


def test_resolve_server_runtime_matches_damage_and_restraint_by_pet_id():
    runtime_skill = {
        "damage_params_by_pet": {"123": 160},
        "restraint_types_by_pet": {"123": 2},
    }
    defender = {"pet_id": 123, "slot": 1, "side": "opp"}

    result = resolve_server_runtime(runtime_skill, defender)

    assert result["power"] == 160
    assert result["power_source"] == "server_damage_params"
    assert result["matched_target_key"] == "123"
    assert result["effectiveness"] == 2.0
    assert result["effectiveness_source"] == "server_restraint_types"


def test_resolve_server_runtime_uses_single_hidden_target_damage_param():
    runtime_skill = {
        "damage_params_by_pet": {"real-pet": 120},
        "restraint_types_by_pet": {"real-pet": -1},
    }
    defender = {"pet_id": 20000000}

    result = resolve_server_runtime(runtime_skill, defender)

    assert result["power"] == 120
    assert result["matched_target_key"] == "real-pet"
    assert result["effectiveness"] == 0.5


def test_resolve_server_runtime_falls_back_to_damage_param_result():
    runtime_skill = {"damage_param_result": 88}

    result = resolve_server_runtime(runtime_skill, {"pet_id": 123})

    assert result["power"] == 88
    assert result["power_source"] == "server_damage_param_result"
    assert result["effectiveness_source"] == "type_chart"


def test_apply_server_power_rule_applies_valid_multiplier_rule():
    server_runtime = {
        "power": 160,
        "power_source": "server_damage_params",
        "matched_target_key": "123",
        "has_damage_params": True,
    }
    rules = {
        "7700001": {
            "enabled": True,
            "mode": "multiplier_over_base_power",
            "requires_matched_target": True,
            "max_power_ratio": 3.0,
        }
    }

    apply_server_power_rule(server_runtime, {"id": 7700001}, base_power=80, server_power_rules=rules)

    assert server_runtime["server_power_applied"] is True
    assert server_runtime["server_power_multiplier"] == 2.0
    assert server_runtime["server_power_skip_reason"] is None


def test_apply_server_power_rule_keeps_skip_reason_when_ratio_is_too_large():
    server_runtime = {
        "power": 400,
        "power_source": "server_damage_params",
        "matched_target_key": "123",
        "has_damage_params": True,
    }
    rules = {
        "7700001": {
            "enabled": True,
            "mode": "multiplier_over_base_power",
            "max_power_ratio": 3.0,
        }
    }

    apply_server_power_rule(server_runtime, {"id": 7700001}, base_power=80, server_power_rules=rules)

    assert server_runtime["server_power_applied"] is False
    assert server_runtime["server_power_multiplier"] == 5.0
    assert server_runtime["server_power_skip_reason"] == "ratio_exceeded"
