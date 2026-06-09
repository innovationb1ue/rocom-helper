"""战术威胁目标选择测试。"""
from __future__ import annotations

from src.analysis.tactical import threats
from src.game.type_chart import TypeChart


def _pet(name: str, pet_id: int = 1) -> dict:
    return {
        "name": name,
        "pet_id": pet_id,
        "current_hp": 100,
        "types": [1],
        "base_speed": 100,
        "stats": [{"name": "ATK", "total": 120}],
        "equipped_skills": [
            {"skill_id": 7020370, "skill_name": "撞击", "skill_element": 1},
        ],
    }


def test_top_threat_name_returns_none_without_opponents():
    assert threats.top_threat_name([], _pet("我方"), chart=TypeChart()) is None


def test_top_threat_name_uses_assessor_target_order():
    class FakeAssessor:
        def suggest_target_order(self, opponent_team, my_active):
            assert opponent_team[0]["name"] == "低威胁"
            assert my_active["skills"][0]["name"] == "撞击"
            return [{"name": "高威胁"}, {"name": "低威胁"}]

    result = threats.top_threat_name(
        [_pet("低威胁", pet_id=2), _pet("高威胁", pet_id=3)],
        _pet("我方"),
        chart=TypeChart(),
        assessor=FakeAssessor(),
    )

    assert result == "高威胁"


def test_top_threat_name_returns_none_when_assessor_has_no_order():
    class EmptyAssessor:
        def suggest_target_order(self, _opponent_team, _my_active):
            return []

    assert threats.top_threat_name(
        [_pet("敌方", pet_id=2)],
        _pet("我方"),
        chart=TypeChart(),
        assessor=EmptyAssessor(),
    ) is None
