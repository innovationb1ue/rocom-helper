"""战术换宠目标推断测试。"""
from __future__ import annotations

from src.analysis.models import OpponentAction
from src.analysis.tactical import switch_targets
from src.game.type_chart import TypeChart


def _pet(name: str, hp: int = 100, pet_id: int = 1, types: list[int] | None = None) -> dict:
    return {
        "name": name,
        "pet_id": pet_id,
        "base_id": 1000 + pet_id,
        "current_hp": hp,
        "max_hp": 100,
        "base_speed": 88,
        "types": types or [1],
        "stats": [
            {"name": "ATK", "total": 120},
            {"name": "DEF", "calc": 80},
        ],
        "equipped_skills": [
            {"skill_id": 7020370, "skill_name": "撞击", "skill_element": 1},
        ],
    }


def test_normalize_pet_for_analysis_maps_stats_speed_and_skills():
    normalized = switch_targets.normalize_pet_for_analysis(_pet("我方", pet_id=1))

    assert normalized["stats"]["ATK"] == 120
    assert normalized["stats"]["DEF"] == 80
    assert normalized["stats"]["SPE"] == 88
    assert normalized["skills"][0]["name"] == "撞击"
    assert normalized["skills"][0]["type_id"] == 1


def test_most_likely_switch_target_prefers_named_living_target():
    resolver = switch_targets.SwitchTargetResolver(TypeChart())
    target = _pet("目标", hp=50, pet_id=2)

    result = resolver.most_likely_switch_target(
        OpponentAction(action_type="switch", switch_to_name="目标", probability=1.0),
        [_pet("当前", pet_id=1), target],
        _pet("我方", pet_id=9),
    )

    assert result is target


def test_most_likely_switch_target_uses_counter_when_named_target_is_dead():
    class FakeCounter:
        def find_counters(self, _my_team, candidates, top_n=1):
            assert top_n == 1
            return [next(candidate for candidate in candidates if candidate["name"] == "反制宠")]

    resolver = switch_targets.SwitchTargetResolver(TypeChart())
    resolver._counter = FakeCounter()
    fallback = _pet("普通替补", hp=100, pet_id=2)
    counter = _pet("反制宠", hp=100, pet_id=3)

    result = resolver.most_likely_switch_target(
        OpponentAction(action_type="switch", switch_to_name="目标", probability=1.0),
        [_pet("目标", hp=0, pet_id=4), fallback, counter],
        _pet("我方", pet_id=9),
    )

    assert result is counter


def test_most_likely_switch_target_returns_none_without_living_candidates():
    resolver = switch_targets.SwitchTargetResolver(TypeChart())

    result = resolver.most_likely_switch_target(
        OpponentAction(action_type="switch", probability=1.0),
        [_pet("倒下", hp=0, pet_id=1)],
        _pet("我方", pet_id=9),
    )

    assert result is None
