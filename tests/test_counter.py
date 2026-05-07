"""反制推荐引擎测试。"""
from __future__ import annotations

import pytest
from src.game.type_chart import TypeChart
from src.analysis.counter import CounterPicker


@pytest.fixture(scope="module")
def picker():
    return CounterPicker(TypeChart())


# Opponent: grass/water team
OPP_GRASS = {"id": 10, "name": "草王", "types": [3], "skills": [{"type_id": 3}],
             "stats": {"SPE": 80}}
OPP_WATER = {"id": 11, "name": "水王", "types": [2], "skills": [{"type_id": 2}],
             "stats": {"SPE": 90}}

POOL = [
    {"id": 20, "name": "火龙", "types": [1], "skills": [{"type_id": 1, "power": 90}],
     "stats": {"SPE": 100}},
    {"id": 21, "name": "电鼠", "types": [4], "skills": [{"type_id": 4, "power": 80}],
     "stats": {"SPE": 110}},
    {"id": 22, "name": "草蛇", "types": [3], "skills": [{"type_id": 3, "power": 85}],
     "stats": {"SPE": 95}},
    {"id": 23, "name": "普通兽", "types": [0], "skills": [{"type_id": 0, "power": 80}],
     "stats": {"SPE": 70}},
]


class TestFindCounters:
    def test_returns_sorted(self, picker):
        counters = picker.find_counters([OPP_GRASS, OPP_WATER], POOL)
        assert len(counters) > 0
        for i in range(len(counters) - 1):
            assert counters[i]["_counter_score"] >= counters[i + 1]["_counter_score"]

    def test_fire_counters_grass(self, picker):
        counters = picker.find_counters([OPP_GRASS], POOL)
        names = [c["name"] for c in counters]
        assert "火龙" in names

    def test_electric_counters_water(self, picker):
        counters = picker.find_counters([OPP_WATER], POOL)
        names = [c["name"] for c in counters]
        assert "电鼠" in names

    def test_empty_opponent(self, picker):
        assert picker.find_counters([], POOL) == []

    def test_empty_pool(self, picker):
        assert picker.find_counters([OPP_GRASS], []) == []

    def test_top_n(self, picker):
        counters = picker.find_counters([OPP_GRASS, OPP_WATER], POOL, top_n=2)
        assert len(counters) <= 2

    def test_counter_detail(self, picker):
        counters = picker.find_counters([OPP_GRASS], POOL)
        fire = next(c for c in counters if c["name"] == "火龙")
        assert "_counter_detail" in fire


class TestFindCounterSkills:
    def test_best_skill(self, picker):
        my_pet = {"types": [1], "skills": [
            {"name": "火焰冲击", "type_id": 1, "power": 80},
            {"name": "普通攻击", "type_id": 0, "power": 60},
        ]}
        opponent = {"types": [3]}  # grass
        skills = picker.find_counter_skills(my_pet, opponent)
        assert len(skills) == 2
        assert skills[0]["name"] == "火焰冲击"
        assert skills[0]["_effectiveness"] == 2.0

    def test_no_skills(self, picker):
        my_pet = {"types": [1], "skills": []}
        opponent = {"types": [3]}
        assert picker.find_counter_skills(my_pet, opponent) == []
