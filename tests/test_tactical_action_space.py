"""战术动作空间枚举测试。"""
from __future__ import annotations

from src.analysis.tactical import action_space, runtime


def _make_pet(
    *,
    name: str = "测试宠",
    pet_id: int = 1,
    hp: int = 300,
    energy: int = 10,
    equipped_skills=None,
) -> dict:
    if equipped_skills is None:
        equipped_skills = [
            {"skill_id": 7020370, "skill_name": "撞击", "skill_damage_type": 2, "skill_element": 1, "cost_energy": 1},
        ]
    return {
        "name": name,
        "pet_id": pet_id,
        "current_hp": hp,
        "max_hp": 300,
        "energy": energy,
        "types": [1],
        "equipped_skills": equipped_skills,
    }


def test_enumerate_our_actions_filters_energy_and_cd_then_adds_switches():
    active = _make_pet(
        pet_id=1,
        energy=3,
        equipped_skills=[
            {"skill_id": 7020370, "skill_name": "可用", "skill_damage_type": 2, "skill_element": 1, "cost_energy": 1},
            {"skill_id": 7020970, "skill_name": "冷却", "skill_damage_type": 2, "skill_element": 1, "cost_energy": 1},
            {"skill_id": 7021030, "skill_name": "高耗", "skill_damage_type": 2, "skill_element": 1, "cost_energy": 8},
        ],
    )
    active["skill_runtime"] = {"7020970": {"cd_round": 2}}
    bench = _make_pet(name="替补", pet_id=2)
    dead = _make_pet(name="战败", pet_id=3, hp=0)

    actions = action_space.enumerate_our_actions(active, [active, bench, dead])

    assert [a.get("skill_name") for a in actions if a["action_type"] == "skill"] == ["可用"]
    assert [a.get("switch_to_name") for a in actions if a["action_type"] == "switch"] == ["替补"]


def test_enumerate_our_actions_uses_runtime_energy_cost():
    active = _make_pet(
        energy=1,
        equipped_skills=[
            {"skill_id": 7020970, "skill_name": "实时耗能", "skill_damage_type": 2, "skill_element": 1, "cost_energy": 5},
        ],
    )
    active["skill_runtime"] = {"7020970": {"cost_energy_result": 1}}

    actions = action_space.enumerate_our_actions(active, [active])

    assert len(actions) == 1
    assert actions[0]["energy_cost"] == 1


def test_runtime_priority_prefers_runtime_then_description():
    assert runtime.skill_priority_layer({}, {"skill_buff": {"priority": 3}}, {}) == 3
    assert runtime.skill_priority_layer({"skill_desc": "先手 +2"}, {}, {}) == 2
    assert runtime.skill_priority_layer({"priority_display": True}, {}, {}) == 1
