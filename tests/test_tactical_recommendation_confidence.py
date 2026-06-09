"""战术推荐置信度测试。"""
from __future__ import annotations

from src.analysis.tactical import recommendation_confidence, recommendations


def test_assess_confidence_prefers_equipped_then_revealed_skills():
    assert recommendation_confidence.assess_confidence({"equipped_skills": [{"skill_id": 1}]}) == "high"
    assert recommendation_confidence.assess_confidence({"skills": [{"skill_id": 1}]}) == "high"
    assert recommendation_confidence.assess_confidence({"used_skills": [{"skill_id": 1}, {"skill_id": 2}, {"skill_id": 3}]}) == "high"
    assert recommendation_confidence.assess_confidence({"used_skills": [{"skill_id": 1}]}) == "medium"
    assert recommendation_confidence.assess_confidence({}) == "low"


def test_recommendations_confidence_facade_stays_compatible():
    assert recommendations.assess_confidence({"used_skills": [{"skill_id": 1}]}) == "medium"
