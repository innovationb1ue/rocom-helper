"""队伍分析和推荐测试。"""
from __future__ import annotations

import pytest
from src.game.type_chart import TypeChart
from src.analysis.team_builder import TeamBuilder


@pytest.fixture(scope="module")
def builder():
    return TeamBuilder(TypeChart())


PETS = [
    {"id": 1, "name": "火龙", "types": [1], "skills": [{"type_id": 1, "power": 90}],
     "stats": {"ATK": 120, "SPA": 100, "SPE": 110, "HP": 80}},
    {"id": 2, "name": "水龟", "types": [2], "skills": [{"type_id": 2, "power": 85}],
     "stats": {"ATK": 80, "SPA": 100, "SPE": 60, "HP": 150}},
    {"id": 3, "name": "草蛇", "types": [3], "skills": [{"type_id": 3, "power": 80}],
     "stats": {"ATK": 90, "SPA": 130, "SPE": 100, "HP": 90}},
]

POOL = [
    {"id": 10, "name": "电鼠", "types": [4], "skills": [{"type_id": 4, "power": 80}],
     "stats": {"SPE": 120}},
    {"id": 11, "name": "翼鹰", "types": [9], "skills": [{"type_id": 9, "power": 85}],
     "stats": {"SPE": 115}},
    {"id": 12, "name": "冰狐", "types": [5], "skills": [{"type_id": 5, "power": 90}],
     "stats": {"SPE": 105}},
    {"id": 13, "name": "幽灵", "types": [13], "skills": [{"type_id": 13, "power": 80}],
     "stats": {"SPE": 90}},
]


class TestAnalyzeTeam:
    def test_basic_analysis(self, builder):
        result = builder.analyze_team(PETS)
        assert "score" in result
        assert 0.0 <= result["score"] <= 100.0

    def test_offensive_coverage(self, builder):
        result = builder.analyze_team(PETS)
        off = result["offensive_coverage"]
        assert len(off) > 0
        # Fire+Water+Grass covers fire/grass/water effectively
        assert off.get("火", 0) >= 2.0
        assert off.get("草", 0) >= 2.0
        assert off.get("水", 0) >= 2.0

    def test_speed_tier(self, builder):
        result = builder.analyze_team(PETS)
        tier = result["speed_tier"]
        assert len(tier) == 3
        assert tier[0]["speed"] >= tier[1]["speed"]

    def test_role_analysis(self, builder):
        result = builder.analyze_team(PETS)
        roles = result["role_analysis"]
        assert len(roles) == 3
        names = [r["name"] for r in roles]
        assert "火龙" in names

    def test_suggestions_generated(self, builder):
        result = builder.analyze_team(PETS)
        assert isinstance(result["suggestions"], list)


class TestSuggestTeammates:
    def test_returns_candidates(self, builder):
        mates = builder.suggest_teammates(PETS[:2], POOL, top_n=3)
        assert len(mates) > 0
        assert len(mates) <= 3

    def test_scored_and_sorted(self, builder):
        mates = builder.suggest_teammates(PETS[:1], POOL)
        for i in range(len(mates) - 1):
            assert mates[i]["_teammate_score"] >= mates[i + 1]["_teammate_score"]

    def test_empty_core(self, builder):
        assert builder.suggest_teammates([], POOL) == []

    def test_empty_pool(self, builder):
        assert builder.suggest_teammates(PETS, []) == []
