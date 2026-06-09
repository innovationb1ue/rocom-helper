"""Buff 效果遍历 helper 的单元测试。"""
from __future__ import annotations

from src.data.buff_effects import (
    buff_stage,
    coerce_buff_id,
    collect_effective_buff_ids,
    iter_derived_buffs,
    iter_effective_buff_ids,
)


def test_coerce_buff_id_accepts_common_shapes():
    assert coerce_buff_id(123) == 123
    assert coerce_buff_id("456") == 456
    assert coerce_buff_id({"buff_id": 789}) == 789
    assert coerce_buff_id({"effect_id": "321"}) == 321
    assert coerce_buff_id({"id": None}) is None


def test_buff_stage_clamps_invalid_and_zero_to_one():
    assert buff_stage({"stage": 3}) == 3
    assert buff_stage({"stage": 0}) == 1
    assert buff_stage({"stage": "bad"}) == 1


def test_iter_derived_buffs_normalizes_raw_ids():
    assert list(iter_derived_buffs({"derived_buffs": [1, {"id": 2}]})) == [{"id": 1}, {"id": 2}]


def test_collect_effective_buff_ids_preserves_repeated_child_effects():
    assert collect_effective_buff_ids(20171870, include_children=True) == [
        (20171870, 20171870),
        (20230440, 20171870),
        (20230440, 20171870),
    ]


def test_iter_effective_buff_ids_does_not_expand_top_level_selector_without_derived_child():
    assert list(iter_effective_buff_ids([{"id": 20890020, "name": "折射"}])) == [
        (20890020, 20890020, {"id": 20890020, "name": "折射"}),
    ]


def test_iter_effective_buff_ids_expands_explicit_derived_child():
    buff = {"id": 20890020, "derived_buffs": [{"id": 20171870, "source_skill": "折射"}]}
    ids = [(item_id, root_id, source.get("source_skill")) for item_id, root_id, source in iter_effective_buff_ids([buff])]

    assert ids == [
        (20890020, 20890020, None),
        (20171870, 20171870, "折射"),
        (20230440, 20171870, "折射"),
        (20230440, 20171870, "折射"),
    ]
