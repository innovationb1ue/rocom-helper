"""资源与技能状态投影测试。"""
from __future__ import annotations

from src.analysis.projection.resources import (
    project_combo_skill_cast,
    project_energy,
    project_skill_cast,
)


def test_project_energy_uses_after_or_delta_and_clamps():
    state = {"my_active": {"energy": 3}, "opp_active": {"energy": 9}}

    project_energy(state, {"target_side": 1, "energy_delta": 20})
    project_energy(state, {"target_side": 401, "energy_after": 6})

    assert state["my_active"]["energy"] == 10
    assert state["opp_active"]["energy"] == 6


def test_project_skill_cast_records_skill_once_and_updates_energy():
    state = {"my_active": {"energy": 5, "used_skills": []}}
    entry = {
        "actor_side": 1,
        "skill_id": 7700001,
        "skill_name": "火焰冲击",
        "energy_after": 2,
    }

    project_skill_cast(state, entry)
    project_skill_cast(state, entry)

    assert state["my_active"]["energy"] == 2
    assert state["my_active"]["used_skills"] == [
        {"skill_id": 7700001, "skill_name": "火焰冲击"}
    ]


def test_project_combo_skill_cast_sets_combo_bonus():
    state = {"my_active": {"combo_bonus": 0}}

    project_combo_skill_cast(state, {"actor_side": 1, "combo_count": 4})

    assert state["my_active"]["combo_bonus"] == 4

