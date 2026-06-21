"""伤害基础公式测试。"""
from __future__ import annotations

from src.analysis.damage.formula import base_damage
from src.analysis.damage_calc import DamageCalculator


def test_base_damage_uses_nrc_formula():
    assert base_damage(200, 100, 80) == 144.0


def test_base_damage_clamps_zero_or_negative_defense():
    assert base_damage(200, 0, 80) == 14400.0
    assert base_damage(200, -10, 80) == 14400.0


def test_damage_calculator_static_base_damage_keeps_compatibility():
    assert DamageCalculator._base_damage(200, 100, 80) == base_damage(200, 100, 80)
