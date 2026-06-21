"""Skill resolver behavior for asymmetric PvP data."""
from __future__ import annotations

from src.analysis.skill_resolver import resolve_opponent_skills


def test_opponent_used_skills_take_priority_over_protocol_candidates():
    pet = {
        "used_skills": [{"skill_id": 1, "skill_name": "闪击"}],
        "battle_skill_pool": [{"skill_id": 2, "skill_name": "虹光冲击"}],
        "base_skill_pool": [{"skill_id": 3, "skill_name": "超导"}],
    }

    skills, source = resolve_opponent_skills(pet)

    assert source == "used"
    assert skills == [{"skill_id": 1, "skill_name": "闪击"}]
