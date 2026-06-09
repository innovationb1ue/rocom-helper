"""对手行动模型测试。"""
from __future__ import annotations

from src.analysis.tactical import opponent_model
from src.game.type_chart import TypeChart


def _make_pet(
    *,
    name: str = "敌方",
    pet_id: int = 101,
    hp: int = 300,
    energy: int = 10,
    types=None,
    equipped_skills=None,
    used_skills=None,
) -> dict:
    if types is None:
        types = [1]
    if equipped_skills is None:
        equipped_skills = [
            {"skill_id": 7020370, "skill_name": "撞击", "skill_damage_type": 2, "skill_element": 1, "cost_energy": 1},
        ]
    return {
        "name": name,
        "pet_id": pet_id,
        "current_hp": hp,
        "max_hp": 300,
        "hp_pct": hp / 300,
        "energy": energy,
        "types": types,
        "equipped_skills": equipped_skills,
        "used_skills": used_skills or [],
    }


def test_compute_skill_probabilities_filters_cd_and_energy():
    opp = _make_pet(
        energy=1,
        equipped_skills=[
            {"skill_id": 7020370, "skill_name": "可用", "skill_damage_type": 2, "skill_element": 1, "cost_energy": 1},
            {"skill_id": 7020970, "skill_name": "冷却", "skill_damage_type": 2, "skill_element": 1, "cost_energy": 1},
            {"skill_id": 7021030, "skill_name": "高耗", "skill_damage_type": 2, "skill_element": 1, "cost_energy": 8},
        ],
    )
    opp["skill_runtime"] = {"7020970": {"cd_round": 1}}

    probs = opponent_model.compute_skill_probabilities(opp["equipped_skills"], opp["energy"], opp)

    assert [(skill_id, name) for skill_id, _prob, name in probs] == [(7020370, "可用")]


def test_estimate_switch_probability_raises_for_low_hp():
    chart = TypeChart()
    low = _make_pet(hp=50)
    full = _make_pet(hp=300)
    state = {"my_active": _make_pet(name="我方", pet_id=1), "opp_active": low}

    assert opponent_model.estimate_switch_probability(low, state, chart=chart) >= (
        opponent_model.estimate_switch_probability(full, state, chart=chart)
    )


def test_predict_opponent_actions_normalizes_and_marks_threat():
    chart = TypeChart()
    my_active = _make_pet(name="我方", pet_id=1, hp=40)
    opp = _make_pet(hp=80)
    bench = _make_pet(name="替补", pet_id=102, hp=300)
    state = {"my_active": my_active, "opp_active": opp, "weather": None}

    def fake_damage(_attacker, _defender, skill_meta, _weather):
        return 50 if skill_meta else 0

    actions = opponent_model.predict_opponent_actions(
        opp,
        [opp, bench],
        state,
        chart=chart,
        calc_damage=fake_damage,
    )

    assert actions
    assert abs(sum(action.probability for action in actions) - 1.0) < 0.001
    assert any(action.action_type == "switch" and action.switch_to_name == "替补" for action in actions)
    skill_actions = [action for action in actions if action.action_type == "skill"]
    assert skill_actions
    assert all(action.threat_damage == 50 for action in skill_actions)
    assert all(action.can_ko is True for action in skill_actions)
