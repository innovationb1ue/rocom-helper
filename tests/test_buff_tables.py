"""Buff 修正底层表构建/cache 的单元测试。"""
from __future__ import annotations

from src.data.buff_tables import (
    get_buff_child_table,
    get_buff_damage_reduction_table,
    get_buff_stat_table,
    get_speed_buff_table,
    reset_buff_tables,
)


def test_buff_stat_table_uses_real_buffbase_data_and_caches_result():
    reset_buff_tables()

    first = get_buff_stat_table()
    second = get_buff_stat_table()

    assert first is second
    assert first[20011521] == {"atk_up": 0.1, "spa_up": 0.1}
    assert first[20010010] == {"atk_up": 0.1}


def test_buff_child_table_preserves_repeated_child_effects():
    reset_buff_tables()

    child_table = get_buff_child_table()

    assert child_table[20171870] == [20230440, 20230440]
    assert child_table[20172000] == [20450050]
    assert 20640260 in child_table[20890020]


def test_speed_and_damage_reduction_tables_are_cached_and_queryable():
    reset_buff_tables()

    speed_first = get_speed_buff_table()
    speed_second = get_speed_buff_table()
    reduction_first = get_buff_damage_reduction_table()
    reduction_second = get_buff_damage_reduction_table()

    assert speed_first is speed_second
    assert reduction_first is reduction_second
    assert speed_first[20010011] == {"flat": 0.0, "pct": 0.2}
    assert reduction_first[20110050] == {"reduction": 0.8, "damage_types": [2, 3]}


def test_reset_buff_tables_rebuilds_cached_objects():
    reset_buff_tables()
    stat_before = get_buff_stat_table()
    child_before = get_buff_child_table()
    reset_buff_tables()

    assert get_buff_stat_table() is not stat_before
    assert get_buff_child_table() is not child_before
