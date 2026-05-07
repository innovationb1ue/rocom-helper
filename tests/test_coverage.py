"""覆盖度分析测试 — 使用真实属性克制数据。"""
from __future__ import annotations

import pytest
from src.game.type_chart import TypeChart
from src.analysis.coverage import CoverageAnalyzer


@pytest.fixture(scope="module")
def analyzer():
    return CoverageAnalyzer(TypeChart())


# Sample pets with type IDs from type_chart.json
FIRE_PET = {"id": 1, "name": "火精灵", "types": [1], "skills": [{"type_id": 1}]}
WATER_PET = {"id": 2, "name": "水精灵", "types": [2], "skills": [{"type_id": 2}]}
GRASS_PET = {"id": 3, "name": "草精灵", "types": [3], "skills": [{"type_id": 3}]}
ELECTRIC_PET = {"id": 4, "name": "电精灵", "types": [4], "skills": [{"type_id": 4}]}
GROUND_PET = {"id": 5, "name": "土精灵", "types": [8], "skills": [{"type_id": 8}]}
FLYING_PET = {"id": 6, "name": "翼精灵", "types": [9], "skills": [{"type_id": 9}]}
DUAL_PET = {"id": 7, "name": "火飞", "types": [1, 9], "skills": [{"type_id": 1}, {"type_id": 9}]}


class TestOffensiveCoverage:
    def test_single_fire_coverage(self, analyzer):
        cov = analyzer.offensive_coverage([FIRE_PET])
        assert cov["草"] == 2.0
        assert cov["火"] == 0.5  # resisted

    def test_dual_coverage(self, analyzer):
        cov = analyzer.offensive_coverage([DUAL_PET])
        assert cov["草"] == 2.0  # fire hits grass
        assert cov["武"] == 2.0  # flying hits fighting

    def test_multi_pet_coverage(self, analyzer):
        cov = analyzer.offensive_coverage([FIRE_PET, WATER_PET, GRASS_PET])
        # Fire beats grass, water beats fire, grass beats water → triangle covered
        assert cov["火"] == 2.0
        assert cov["水"] == 2.0
        assert cov["草"] == 2.0

    def test_empty_team(self, analyzer):
        cov = analyzer.offensive_coverage([])
        # Falls back to all types
        assert len(cov) > 0


class TestDefensiveCoverage:
    def test_fire_weakness(self, analyzer):
        dc = analyzer.defensive_coverage([FIRE_PET])
        assert "水" in dc
        assert "火精灵" in dc["水"]

    def test_no_shared_weakness(self, analyzer):
        dc = analyzer.defensive_coverage([FIRE_PET, ELECTRIC_PET])
        # Fire weak to water/ground/rock; Electric weak to ground only
        # Only ground is shared
        shared = {k: v for k, v in dc.items() if len(v) >= 2}
        assert "土" in shared

    def test_dual_type_weakness(self, analyzer):
        dc = analyzer.defensive_coverage([DUAL_PET])
        # Fire/Flying weak to water, electric, rock
        assert "水" in dc or "电" in dc or "石" in dc


class TestCoverageScore:
    def test_score_range(self, analyzer):
        score = analyzer.coverage_score([FIRE_PET, WATER_PET, GRASS_PET])
        assert 0.0 <= score <= 100.0

    def test_better_team_higher_score(self, analyzer):
        team1 = [FIRE_PET]
        team2 = [FIRE_PET, WATER_PET, GRASS_PET, ELECTRIC_PET, GROUND_PET]
        s1 = analyzer.coverage_score(team1)
        s2 = analyzer.coverage_score(team2)
        assert s2 > s1


class TestUncoveredTypes:
    def test_fire_uncovered(self, analyzer):
        unc = analyzer.uncovered_types([FIRE_PET])
        # Fire doesn't cover many types
        assert len(unc) > 0

    def test_full_coverage(self, analyzer):
        unc = analyzer.uncovered_types([FIRE_PET, WATER_PET, GRASS_PET, ELECTRIC_PET, GROUND_PET, FLYING_PET])
        # Good coverage team should have fewer uncovered types
        # (may still have some like divine types)
        assert len(unc) < len(analyzer.uncovered_types([FIRE_PET]))


class TestSharedWeaknesses:
    def test_fire_electric_shared_ground(self, analyzer):
        sw = analyzer.shared_weaknesses([FIRE_PET, ELECTRIC_PET])
        # Both weak to ground (土)
        assert "土" in sw

    def test_two_fire_pets_shared(self, analyzer):
        sw = analyzer.shared_weaknesses([FIRE_PET, {"id": 8, "name": "火2", "types": [1], "skills": []}])
        # Both fire → shared weakness to water, ground, rock
        assert "水" in sw or "土" in sw or "石" in sw
