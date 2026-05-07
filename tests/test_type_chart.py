"""属性克制计算器测试 — 使用真实 type_chart.json 数据。"""
from __future__ import annotations

import pytest
from src.game.type_chart import TypeChart


@pytest.fixture(scope="module")
def chart():
    return TypeChart()


class TestChartLoading:
    def test_loads_successfully(self, chart):
        assert chart.version == "2.0"
        assert len(chart.types) == 18

    def test_all_types_have_ids(self, chart):
        ids = [t["id"] for t in chart.all_types()]
        assert len(ids) == 18
        assert 0 in ids   # 普通
        assert 11 in ids  # 幻
        assert 17 in ids  # 光

    def test_type_name_lookup(self, chart):
        assert chart.type_name(0) == "普通"
        assert chart.type_name(1) == "火"
        assert chart.type_name(2) == "水"
        assert chart.type_name(3) == "草"
        assert chart.type_name(8) == "地"
        assert chart.type_name(13) == "幽"
        assert chart.type_name(16) == "恶"
        assert chart.type_name(11) == "幻"

    def test_type_id_lookup(self, chart):
        assert chart.type_id("火") == 1
        assert chart.type_id("水") == 2
        assert chart.type_id("地") == 8
        assert chart.type_id("幽") == 13
        assert chart.type_id("恶") == 16
        assert chart.type_id("幻") == 11

    def test_type_color(self, chart):
        c = chart.type_color(1)
        assert isinstance(c, str)
        assert c.startswith("#")


class TestSingleTypeMatchups:
    """单属性克制关系测试 — 基于 BWIKI 权威数据。"""

    def test_fire_beats_grass(self, chart):
        assert chart.get_multiplier(1, [3]) == 2.0

    def test_fire_beats_ice(self, chart):
        assert chart.get_multiplier(1, [5]) == 2.0

    def test_fire_beats_bug(self, chart):
        assert chart.get_multiplier(1, [12]) == 2.0

    def test_fire_beats_machine(self, chart):
        assert chart.get_multiplier(1, [14]) == 2.0

    def test_water_beats_fire(self, chart):
        assert chart.get_multiplier(2, [1]) == 2.0

    def test_water_beats_ground(self, chart):
        assert chart.get_multiplier(2, [8]) == 2.0

    def test_water_beats_machine(self, chart):
        assert chart.get_multiplier(2, [14]) == 2.0

    def test_grass_beats_water(self, chart):
        assert chart.get_multiplier(3, [2]) == 2.0

    def test_grass_beats_light(self, chart):
        assert chart.get_multiplier(3, [17]) == 2.0

    def test_grass_beats_ground(self, chart):
        assert chart.get_multiplier(3, [8]) == 2.0

    def test_electric_beats_water(self, chart):
        assert chart.get_multiplier(4, [9]) == 2.0

    def test_electric_beats_flying(self, chart):
        assert chart.get_multiplier(4, [9]) == 2.0

    def test_electric_vs_ground_is_resisted(self, chart):
        assert chart.get_multiplier(4, [8]) == 0.5

    def test_ice_beats_dragon(self, chart):
        assert chart.get_multiplier(5, [15]) == 2.0

    def test_ice_beats_flying(self, chart):
        assert chart.get_multiplier(5, [9]) == 2.0

    def test_fighting_beats_normal(self, chart):
        assert chart.get_multiplier(6, [0]) == 2.0

    def test_fighting_beats_dark(self, chart):
        assert chart.get_multiplier(6, [16]) == 2.0

    def test_fighting_beats_machine(self, chart):
        assert chart.get_multiplier(6, [14]) == 2.0

    def test_ghost_vs_normal_is_resisted(self, chart):
        assert chart.get_multiplier(13, [0]) == 0.5

    def test_fighting_vs_ghost_is_resisted(self, chart):
        assert chart.get_multiplier(6, [13]) == 0.5

    def test_fire_resisted_by_dragon(self, chart):
        assert chart.get_multiplier(1, [15]) == 0.5

    def test_grass_resisted_by_dragon(self, chart):
        assert chart.get_multiplier(3, [15]) == 0.5

    def test_grass_resisted_by_machine(self, chart):
        assert chart.get_multiplier(3, [14]) == 0.5


class TestDualTypeMatchups:
    """双属性克制关系测试。"""

    def test_double_weakness(self, chart):
        # 草/地 vs 冰：草被冰×2.0, 地被冰×2.0 → 2.0*2.0=4.0
        assert chart.get_multiplier(5, [3, 8]) == pytest.approx(4.0)

    def test_double_resistance(self, chart):
        # 毒 vs 草/毒：草×2.0 * 毒×0.5 = 1.0
        assert chart.get_multiplier(7, [3, 7]) == pytest.approx(1.0)

    def test_water_vs_fire_flying(self, chart):
        # 水→火(2.0) * 水→翼(1.0) = 2.0
        assert chart.get_multiplier(2, [1, 9]) == pytest.approx(2.0)

    def test_electric_vs_water_flying(self, chart):
        # 电→水(2.0) * 电→翼(2.0) = 4.0
        assert chart.get_multiplier(4, [2, 9]) == pytest.approx(4.0)

    def test_resistance_cancels_weakness(self, chart):
        # 水 vs 草/火：草被水×0.5, 火被水×2.0 → 0.5*2.0=1.0
        assert chart.get_multiplier(2, [3, 1]) == pytest.approx(1.0)

    def test_fire_vs_water_dragon(self, chart):
        # 火→水(0.5) * 火→龙(0.5) = 0.25
        assert chart.get_multiplier(1, [2, 15]) == pytest.approx(0.25)


class TestLightType:
    """光属性测试。"""

    def test_light_beats_ghost(self, chart):
        assert chart.get_multiplier(17, [13]) == 2.0

    def test_light_beats_dark(self, chart):
        assert chart.get_multiplier(17, [16]) == 2.0

    def test_light_resisted_by_grass(self, chart):
        assert chart.get_multiplier(17, [3]) == 0.5

    def test_light_resisted_by_ice(self, chart):
        assert chart.get_multiplier(17, [5]) == 0.5

    def test_light_vs_fire(self, chart):
        assert chart.get_multiplier(17, [1]) == 1.0


class TestIllusionType:
    """幻属性测试。"""

    def test_illusion_beats_poison(self, chart):
        assert chart.get_multiplier(11, [7]) == 2.0

    def test_illusion_beats_fighting(self, chart):
        assert chart.get_multiplier(11, [6]) == 2.0

    def test_illusion_resisted_by_light(self, chart):
        assert chart.get_multiplier(11, [17]) == 0.5

    def test_illusion_resisted_by_machine(self, chart):
        assert chart.get_multiplier(11, [14]) == 0.5

    def test_illusion_resisted_by_self(self, chart):
        assert chart.get_multiplier(11, [11]) == 0.5

    def test_bug_beats_illusion(self, chart):
        assert chart.get_multiplier(12, [11]) == 2.0

    def test_ghost_beats_illusion(self, chart):
        assert chart.get_multiplier(13, [11]) == 2.0


class TestWeaknesses:
    def test_fire_weaknesses(self, chart):
        w = chart.get_weaknesses([1])
        assert 2 in w   # 水克火
        assert 8 in w   # 地克火

    def test_water_weaknesses(self, chart):
        w = chart.get_weaknesses([2])
        assert 3 in w   # 草克水

    def test_ground_weaknesses(self, chart):
        w = chart.get_weaknesses([8])
        assert 3 in w   # 草克地
        assert 2 in w   # 水克地
        assert 5 in w   # 冰克地
        assert 6 in w   # 武克地
        assert 14 in w  # 机械克地

    def test_normal_weaknesses(self, chart):
        w = chart.get_weaknesses([0])
        assert 6 in w  # 武克普通

    def test_illusion_weaknesses(self, chart):
        w = chart.get_weaknesses([11])
        assert 12 in w  # 虫克幻
        assert 13 in w  # 幽克幻


class TestResistances:
    def test_fire_resistances(self, chart):
        r = chart.get_resistances([1])
        assert 3 in r   # 草对火0.5x
        assert 5 in r   # 冰对火0.5x
        assert 12 in r  # 虫对火0.5x

    def test_water_resistances(self, chart):
        r = chart.get_resistances([2])
        assert 1 in r   # 火对水0.5x

    def test_machine_resistances(self, chart):
        r = chart.get_resistances([14])
        assert 14 in r  # 机械对机械0.5x
        assert 3 in r   # 草对机械0.5x
        assert 5 in r   # 冰对机械0.5x
        assert 7 in r   # 毒对机械0.5x

    def test_normal_resistances(self, chart):
        r = chart.get_resistances([0])
        assert 13 in r  # 幽对普通0.5x


class TestImmunities:
    """游戏中没有 0.0x 免疫关系，所有非1.0都是 0.5x 或 2.0x。"""

    def test_no_immunities_for_ground(self, chart):
        im = chart.get_immunities([8])
        assert len(im) == 0

    def test_no_immunities_for_ghost(self, chart):
        im = chart.get_immunities([13])
        assert len(im) == 0

    def test_no_immunities_for_normal(self, chart):
        im = chart.get_immunities([0])
        assert len(im) == 0


class TestCoverage:
    def test_single_type_coverage(self, chart):
        cov = chart.get_coverage([1])  # 火系技能
        assert cov[3] == 2.0  # 火克草
        assert cov[2] == 0.5  # 火被水抗

    def test_multi_type_coverage(self, chart):
        cov = chart.get_coverage([1, 2])  # 火+水
        assert cov[3] == 2.0  # 火克草
        assert cov[1] == 2.0  # 水克火

    def test_coverage_score(self, chart):
        score = chart.offensive_coverage_score([1, 2, 3])
        assert 0.0 <= score <= 100.0
        assert score > 30.0


class TestEffectivenessLabel:
    def test_labels(self, chart):
        assert chart.get_effectiveness_label(0.25) == "效果甚微"
        assert chart.get_effectiveness_label(0.5) == "效果不佳"
        assert chart.get_effectiveness_label(1.0) == "普通"
        assert chart.get_effectiveness_label(1.5) == "效果不错"
        assert chart.get_effectiveness_label(2.0) == "效果拔群"
        assert chart.get_effectiveness_label(4.0) == "超级有效"


class TestDefensiveRating:
    def test_normal_type_rating(self, chart):
        r = chart.defensive_rating([0])
        assert 0.0 <= r <= 100.0

    def test_dual_type_rating(self, chart):
        r = chart.defensive_rating([1, 9])
        assert 0.0 <= r <= 100.0
