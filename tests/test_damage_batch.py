"""批量伤害预测编排测试。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.analysis.damage import batch
from src.analysis.damage.result import DamageResult


def _result(skill_id: int, expected_damage: int, hit_count: int = 1) -> DamageResult:
    return DamageResult(
        skill_id=skill_id,
        skill_name=f"技能{skill_id}",
        power=80,
        effective_power=80,
        damage_type=2,
        skill_element=1,
        skill_element_name="火",
        effectiveness=1.0,
        effectiveness_label="普通",
        is_stab=False,
        expected_damage=expected_damage,
        pct_hp=0.2,
        can_ko=False,
        energy_cost=1,
        confidence="high",
        hit_count=hit_count,
    )


class FakeCalculator:
    def __init__(self) -> None:
        self.seen: list[tuple[int, Optional[Dict[str, Any]]]] = []

    def calculate(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        skill_meta: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
    ) -> Optional[DamageResult]:
        self.seen.append((skill_meta["id"], weather))
        if skill_meta.get("non_damage"):
            return None
        return _result(skill_meta["id"], skill_meta["damage"], skill_meta.get("hits", 1))


def test_calculate_all_skills_skips_missing_meta_and_sorts_by_total_damage(monkeypatch):
    metas = {
        1: {"id": 1, "damage": 20, "hits": 3},
        2: {"id": 2, "damage": 70},
        3: {"id": 3, "damage": 999, "non_damage": True},
    }
    monkeypatch.setattr(batch, "get_skill_meta", lambda skill_id: metas.get(skill_id))
    calc = FakeCalculator()
    weather = {"id": 1}

    results = batch.calculate_all_skills(
        calc,
        {"name": "我方"},
        {"name": "对手"},
        [{"skill_id": 1}, {"skill_id": 404}, {}, {"skill_id": 2}, {"skill_id": 3}],
        weather=weather,
    )

    assert [r.skill_id for r in results] == [2, 1]
    assert calc.seen == [(1, weather), (2, weather), (3, weather)]
