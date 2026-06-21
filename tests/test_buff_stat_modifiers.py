"""Buff 属性修正计算测试。"""
from __future__ import annotations

import pytest

from src.data import buff_modifiers
from src.data.buff_stat_modifiers import (
    _resolve_buff_modifiers,
    get_buff_derived_stat_modifiers,
    get_buff_stat_modifiers,
)


def test_stat_modifiers_apply_stage_and_accumulate():
    result = get_buff_stat_modifiers([
        {"id": 20011521, "stage": 1},
        {"id": 20011521, "stage": 2},
    ])

    assert result == {"atk_up": pytest.approx(0.3), "spa_up": pytest.approx(0.3)}


def test_top_level_selector_does_not_expand_without_explicit_child():
    assert get_buff_stat_modifiers([{"id": 20890020, "name": "折射", "stage": 1}]) == {}


def test_explicit_derived_buff_contributes_stat_modifier():
    buff = {
        "id": 20890020,
        "name": "折射",
        "derived_buffs": [{"id": 20171910, "stage": 1, "name": "光加魔攻"}],
    }

    assert get_buff_derived_stat_modifiers([buff]) == {"spa_up": 0.4}
    assert get_buff_stat_modifiers([buff]) == {"spa_up": 0.4}


def test_resolve_buff_modifiers_is_reexported_for_compatibility():
    assert buff_modifiers._resolve_buff_modifiers is _resolve_buff_modifiers
    assert buff_modifiers.get_buff_stat_modifiers is get_buff_stat_modifiers
    assert buff_modifiers.get_buff_derived_stat_modifiers is get_buff_derived_stat_modifiers
