"""伤害审计共享工具测试。"""
from __future__ import annotations

from src.analysis.damage.audit_utils import (
    first_present,
    has_value,
    optional_int,
    resolve_runtime_cost,
    restraint_to_multiplier,
)


def test_optional_int_handles_missing_invalid_and_numeric_values():
    assert optional_int(None) is None
    assert optional_int("bad") is None
    assert optional_int("12") == 12
    assert optional_int(3.7) == 3


def test_first_present_returns_first_non_none_value():
    assert first_present([{"x": None}, {"x": 0}, {"x": 3}], "x") == 0
    assert first_present([{"y": 1}], "x") is None


def test_has_value_matches_audit_field_presence_semantics():
    assert has_value(None) is False
    assert has_value({}) is False
    assert has_value([]) is False
    assert has_value(0) is True
    assert has_value("") is True


def test_resolve_runtime_cost_uses_runtime_priority_order():
    assert resolve_runtime_cost({"cost_energy_result": "5", "cost_energy": 2}) == 5
    assert resolve_runtime_cost({"cost_energy": "2", "raw_cost_energy": 1}) == 2
    assert resolve_runtime_cost({"raw_cost_energy": "1"}) == 1
    assert resolve_runtime_cost({}) is None


def test_restraint_to_multiplier_maps_protocol_values():
    assert restraint_to_multiplier(-2) == 0.25
    assert restraint_to_multiplier("0") == 1.0
    assert restraint_to_multiplier(3) == 4.0
    assert restraint_to_multiplier("bad") is None
    assert restraint_to_multiplier(99) is None
