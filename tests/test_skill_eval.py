"""技能评分系统测试。"""
from __future__ import annotations

import pytest
from src.game.skill_eval import score_skill, rank_skills


class TestScoreSkill:
    def test_basic_skill(self):
        skill = {
            "power": 80,
            "energy_cost": 3,
            "accuracy": 100,
            "pp": 20,
        }
        score = score_skill(skill)
        assert 0.0 <= score <= 100.0
        assert score > 30.0

    def test_powerful_skill_scores_higher(self):
        weak = {"power": 40, "energy_cost": 3, "accuracy": 100, "pp": 20}
        strong = {"power": 150, "energy_cost": 5, "accuracy": 90, "pp": 5}
        assert score_skill(strong) > score_skill(weak)

    def test_no_power(self):
        skill = {"energy_cost": 3, "accuracy": 100, "pp": 20}
        score = score_skill(skill)
        assert score >= 0.0

    def test_string_power(self):
        skill = {"power": "90", "energy_cost": "3", "accuracy": "100", "pp": "15"}
        score = score_skill(skill)
        assert score > 0.0

    def test_with_effect(self):
        no_effect = {"power": 80, "energy_cost": 3, "accuracy": 100, "pp": 20}
        with_effect = {"power": 80, "energy_cost": 3, "accuracy": 100, "pp": 20,
                       "effect": "降低对手速度"}
        assert score_skill(with_effect) >= score_skill(no_effect)

    def test_with_type_chart(self):
        from src.game.type_chart import TypeChart
        chart = TypeChart()
        # 火系技能 (1) 克制草/虫/冰/机械 — good coverage
        fire_skill = {"power": 80, "energy_cost": 3, "accuracy": 100, "pp": 20,
                      "type_id": 1}
        no_type_skill = {"power": 80, "energy_cost": 3, "accuracy": 100, "pp": 20}
        fire_score = score_skill(fire_skill, chart)
        no_type_score = score_skill(no_type_skill, chart)
        # Fire with type chart should produce a valid score
        assert fire_score > 0.0
        # Skills with a type_id should get a different coverage score than None
        assert fire_score != no_type_score


class TestRankSkills:
    def test_ranking(self):
        skills = [
            {"name": "弱技能", "power": 40, "energy_cost": 3, "accuracy": 100, "pp": 20},
            {"name": "强技能", "power": 120, "energy_cost": 4, "accuracy": 95, "pp": 10},
            {"name": "中技能", "power": 80, "energy_cost": 3, "accuracy": 100, "pp": 15},
        ]
        ranked = rank_skills(skills)
        assert len(ranked) == 3
        assert ranked[0]["name"] == "强技能"
        assert ranked[0]["_score"] >= ranked[1]["_score"]
        assert ranked[1]["_score"] >= ranked[2]["_score"]

    def test_empty_list(self):
        assert rank_skills([]) == []
