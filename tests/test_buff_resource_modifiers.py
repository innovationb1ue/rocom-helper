"""Buff 速度和伤害减免修正测试。"""
from __future__ import annotations

from src.data import buff_modifiers
from src.data.buff_resource_modifiers import (
    get_buff_damage_reduction,
    get_speed_buff_modifiers,
)
from src.data.weather import get_weather_damage_mult


def test_speed_buff_modifiers_apply_stage():
    assert get_speed_buff_modifiers([{"id": 20010011, "stage": 2}]) == {
        "flat_total": 0.0,
        "pct_total": 0.4,
    }


def test_damage_reduction_filters_type_and_caps():
    assert get_buff_damage_reduction([{"id": 20110050, "stage": 2}], damage_type=2) == 0.95
    assert get_buff_damage_reduction([{"id": 20110050, "stage": 1}], damage_type=99) == 0.0


def test_buff_modifiers_keeps_resource_and_weather_reexports():
    assert buff_modifiers.get_speed_buff_modifiers is get_speed_buff_modifiers
    assert buff_modifiers.get_buff_damage_reduction is get_buff_damage_reduction
    assert buff_modifiers.get_weather_damage_mult is get_weather_damage_mult
