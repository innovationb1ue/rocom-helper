from __future__ import annotations

from src.analysis.advisor.suggestions import build_advisor_suggestions
from src.analysis.models import SkillAnalysis
from src.game.type_chart import TypeChart


def _skill(name: str, damage: int, *, can_ko: bool = False, effectiveness: float = 1.0, warnings=None):
    item = SkillAnalysis(
        skill_id=1,
        skill_name=name,
        equipped_slot=1,
        skill_element=1,
        skill_damage_type=2,
        energy_cost=1,
    )
    item.expected_damage = damage
    item.total_max_damage = damage
    item.can_ko = can_ko
    item.effectiveness = effectiveness
    item.warnings = warnings or []
    return item


def test_build_advisor_suggestions_prefers_ko_message():
    suggestions = build_advisor_suggestions(
        chart=TypeChart(),
        my_active={"name": "我方", "types": [1]},
        opp_active={"name": "敌方", "types": [2]},
        skill_analysis=[_skill("终结技", 200, can_ko=True)],
    )

    assert suggestions == [{"type": "ko_skill", "message": "终结技 可以击杀 敌方！"}]


def test_build_advisor_suggestions_marks_all_attack_skills_energy_blocked():
    suggestions = build_advisor_suggestions(
        chart=TypeChart(),
        my_active={"name": "我方", "types": [1]},
        opp_active={"name": "敌方", "types": [2]},
        skill_analysis=[
            _skill("技能A", 30, warnings=["能量不足"]),
            _skill("技能B", 20, warnings=["能量不足"]),
        ],
    )

    assert {"type": "no_energy", "message": "能量不足以使用任何攻击技能"} in suggestions


def test_build_advisor_suggestions_adds_counter_switch_for_resisted_matchup():
    my_active = {"pet_id": 1, "name": "当前", "types": [1], "current_hp": 100}
    bench = {"pet_id": 2, "name": "替补", "types": [2], "current_hp": 100}

    suggestions = build_advisor_suggestions(
        chart=TypeChart(),
        my_active=my_active,
        opp_active={"name": "敌方", "types": [1]},
        skill_analysis=[_skill("被抵抗", 20, effectiveness=0.5)],
        my_pets=[my_active, bench],
    )

    types = [item["type"] for item in suggestions]
    assert "resisted" in types
    assert "counter_switch" in types
