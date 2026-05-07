"""种族值/能力值计算测试。"""
from __future__ import annotations

import pytest
from src.game.stats import (
    calc_hp, calc_stat, get_nature_modifier, calc_all_stats,
    normalize_stat, stat_total, stat_rating, STAT_NAMES, NATURE_EFFECTS,
)


class TestCalcHP:
    def test_basic_calc(self):
        # base=100, iv=31, ev=0, level=100
        # ((100*2 + 31 + 0) * 100 // 100) + 100 + 10 = 231 + 110 = 341
        hp = calc_hp(100, 31, 0, 100)
        assert hp == 341

    def test_with_evs(self):
        # base=100, iv=31, ev=252, level=100
        # ((200 + 31 + 63) * 100 // 100) + 100 + 10 = 294 + 110 = 404
        hp = calc_hp(100, 31, 252, 100)
        assert hp == 404

    def test_low_base(self):
        hp = calc_hp(1, 0, 0, 1)
        assert hp > 0

    def test_level_50(self):
        hp = calc_hp(100, 31, 0, 50)
        assert hp > 0
        assert hp < calc_hp(100, 31, 0, 100)


class TestCalcStat:
    def test_basic_calc(self):
        # base=100, iv=31, ev=0, level=100, modifier=1.0
        # ((200 + 31 + 0) * 100 // 100) + 5 = 236
        stat = calc_stat(100, 31, 0, 100, 1.0)
        assert stat == 236

    def test_with_nature_boost(self):
        neutral = calc_stat(100, 31, 0, 100, 1.0)
        boosted = calc_stat(100, 31, 0, 100, 1.1)
        assert boosted == int(neutral * 1.1)

    def test_with_nature_drop(self):
        neutral = calc_stat(100, 31, 0, 100, 1.0)
        dropped = calc_stat(100, 31, 0, 100, 0.9)
        assert dropped == int(neutral * 0.9)

    def test_with_evs(self):
        stat = calc_stat(100, 31, 252, 100, 1.0)
        # ((200 + 31 + 63) * 100 // 100) + 5 = 299
        assert stat == 299


class TestNatureModifier:
    def test_neutral_nature(self):
        assert get_nature_modifier("坦率", 1) == 1.0
        assert get_nature_modifier("害羞", 3) == 1.0

    def test_boosting_nature(self):
        # 固执: ATK+(1), SPD-(3)
        assert get_nature_modifier("固执", 1) == 1.1
        assert get_nature_modifier("固执", 3) == 0.9
        assert get_nature_modifier("固执", 2) == 1.0

    def test_hp_not_affected(self):
        assert get_nature_modifier("固执", 0) == 1.0

    def test_unknown_nature(self):
        assert get_nature_modifier("未知性格", 1) == 1.0


class TestCalcAllStats:
    def test_six_stats(self):
        bases = [100, 80, 90, 110, 85, 95]
        result = calc_all_stats(bases)
        assert len(result) == 6
        for name in STAT_NAMES:
            assert name in result
            assert result[name] > 0

    def test_invalid_bases_length(self):
        with pytest.raises(ValueError):
            calc_all_stats([100, 80])

    def test_custom_ivs_evs(self):
        bases = [100, 80, 90, 110, 85, 95]
        ivs = [31, 0, 31, 31, 0, 31]
        evs = [252, 0, 0, 252, 0, 4]
        result = calc_all_stats(bases, ivs, evs, level=100, nature="固执")
        assert result["ATK"] > 0
        # ATK should be boosted by 固执
        neutral = calc_stat(80, 0, 0, 100, 1.0)
        boosted = calc_stat(80, 0, 0, 100, 1.1)
        assert result["ATK"] == boosted


class TestNormalizeStat:
    def test_max_value(self):
        assert normalize_stat(300, 300) == 100.0

    def test_half_value(self):
        assert normalize_stat(150, 300) == 50.0

    def test_zero(self):
        assert normalize_stat(0, 300) == 0.0

    def test_over_max_capped(self):
        assert normalize_stat(400, 300) == 100.0


class TestStatTotal:
    def test_total(self):
        assert stat_total([100, 80, 90, 110, 85, 95]) == 560

    def test_rating(self):
        r = stat_rating([100, 80, 90, 110, 85, 95])
        assert 0.0 <= r <= 100.0
        assert r > 80.0  # 560/600 = 93.3
