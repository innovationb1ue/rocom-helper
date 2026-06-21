"""Buff/effect 状态投影测试。"""
from __future__ import annotations

from src.analysis.projection.effects import project_effect_apply, project_effect_stage


def test_project_effect_apply_adds_buff_and_poison_stack():
    state = {"opp_active": {"buffs": [], "poison_stacks": 0}}

    project_effect_apply(
        state,
        {
            "target_side": 401,
            "effect_id": 20070010,
            "effect_stage": 2,
            "effect_name": "中毒",
            "related_skills": [{"skill_name": "毒囊"}],
        },
    )

    buff = state["opp_active"]["buffs"][0]
    assert buff["id"] == 20070010
    assert buff["name"] == "中毒"
    assert buff["source_skill"] == "毒囊"
    assert state["opp_active"]["poison_stacks"] == 2


def test_project_effect_stage_removes_buff():
    state = {"my_active": {"buffs": [{"id": 10, "stage": 1}]}}

    project_effect_stage(state, {"actor_side": 1, "effect_id": 10, "effect_stage": 3})

    assert state["my_active"]["buffs"] == []

