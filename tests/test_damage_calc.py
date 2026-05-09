"""伤害计算器测试 — 验证伤害公式、STAB、属性克制、KO 判定、置信度。"""
from __future__ import annotations

import math

import pytest

from src.analysis.damage_calc import DamageCalculator, DamageResult
from src.game.type_chart import TypeChart


@pytest.fixture(scope="module")
def calc():
    return DamageCalculator(TypeChart())


def _make_attacker(types=None, atk=200, spa=180, level=100, max_hp=300, current_hp=300, energy=10):
    types = types or [1]
    return {
        "types": types,
        "level": level,
        "max_hp": max_hp,
        "current_hp": current_hp,
        "energy": energy,
        "stats": [
            {"name": "ATK", "total": atk},
            {"name": "SPA", "total": spa},
            {"name": "DEF", "total": 150},
            {"name": "SPD", "total": 150},
        ],
    }


def _make_defender(types=None, def_=150, spd=150, max_hp=350, current_hp=350):
    types = types or [2]
    return {
        "types": types,
        "max_hp": max_hp,
        "current_hp": current_hp,
        "stats": [
            {"name": "DEF", "total": def_},
            {"name": "SPD", "total": spd},
        ],
    }


def _make_skill(dam_type=2, power=80, element=1, energy_cost=None):
    if energy_cost is None:
        energy_cost = [3]
    return {
        "id": 7700001,
        "name": "火焰冲击",
        "damage_type": dam_type,
        "dam_para": [power],
        "skill_dam_type": element,
        "energy_cost": energy_cost,
    }


# ---------------------------------------------------------------------------
# TestBaseDamage — 公式: floor((level*0.4 + 2) * power * atk / def / 50 + 2)
# ---------------------------------------------------------------------------


class TestBaseDamage:
    def test_known_values(self):
        # (100*0.4 + 2) * 80 * 200 / 100 / 50 + 2 = 42 * 160 / 50 + 2 = 134.4 + 2 = 136
        result = DamageCalculator._base_damage(100, 80, 200, 100)
        assert result == 136

    def test_level_scaling(self):
        d50 = DamageCalculator._base_damage(50, 80, 200, 100)
        d100 = DamageCalculator._base_damage(100, 80, 200, 100)
        assert d100 > d50

    def test_power_scaling(self):
        d1 = DamageCalculator._base_damage(100, 40, 200, 100)
        d2 = DamageCalculator._base_damage(100, 80, 200, 100)
        assert d2 > d1

    def test_zero_defense_clamps_to_one(self):
        result = DamageCalculator._base_damage(100, 80, 200, 0)
        assert result > 0

    def test_negative_defense_clamps_to_one(self):
        result = DamageCalculator._base_damage(100, 80, 200, -10)
        assert result > 0

    def test_minimum_damage_is_at_least_1(self):
        result = DamageCalculator._base_damage(1, 1, 1, 9999)
        assert result >= 1


# ---------------------------------------------------------------------------
# TestGetPower
# ---------------------------------------------------------------------------


class TestGetPower:
    def test_from_dam_para(self):
        assert DamageCalculator._get_power({"dam_para": [90]}) == 90

    def test_empty_dam_para(self):
        assert DamageCalculator._get_power({"dam_para": []}) == 0

    def test_no_dam_para(self):
        assert DamageCalculator._get_power({}) == 0


# ---------------------------------------------------------------------------
# TestGetStat
# ---------------------------------------------------------------------------


class TestGetStat:
    def test_from_total(self):
        pet = {"stats": [{"name": "ATK", "total": 250}]}
        assert DamageCalculator._get_stat(pet, "ATK") == 250

    def test_from_calc_plus_bonus(self):
        pet = {"stats": [{"name": "ATK", "calc": 200, "bonus": 30}]}
        assert DamageCalculator._get_stat(pet, "ATK") == 230

    def test_missing_stat(self):
        pet = {"stats": [{"name": "DEF", "total": 100}]}
        assert DamageCalculator._get_stat(pet, "ATK") is None

    def test_empty_stats(self):
        assert DamageCalculator._get_stat({"stats": []}, "ATK") is None

    def test_no_stats_key(self):
        assert DamageCalculator._get_stat({}, "ATK") is None


# ---------------------------------------------------------------------------
# TestCalculate — 完整伤害计算
# ---------------------------------------------------------------------------


class TestCalculate:
    def test_physical_damage_uses_atk_def(self, calc):
        result = calc.calculate(
            _make_attacker(atk=300, spa=100),
            _make_defender(def_=100, spd=200),
            _make_skill(dam_type=2),
        )
        assert result is not None
        assert result.damage_type == 2
        assert result.max_damage > result.min_damage

    def test_special_damage_uses_spa_spd(self, calc):
        result = calc.calculate(
            _make_attacker(atk=100, spa=300),
            _make_defender(def_=200, spd=100),
            _make_skill(dam_type=3),
        )
        assert result is not None
        assert result.damage_type == 3

    def test_stab_bonus(self, calc):
        with_stab = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[0]),
            _make_skill(element=1),
        )
        no_stab = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[0]),
            _make_skill(element=2),
        )
        assert with_stab.is_stab is True
        assert no_stab.is_stab is False
        assert with_stab.max_damage > no_stab.max_damage

    def test_stab_ratio(self, calc):
        # STAB = 1.5x, verify ratio approximately
        with_stab = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[0]),
            _make_skill(element=1),
        )
        no_stab = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[0]),
            _make_skill(element=2),
        )
        ratio = with_stab.max_damage / no_stab.max_damage
        assert 1.4 < ratio < 1.6

    def test_effectiveness_super_effective(self, calc):
        result = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[3]),  # 草
            _make_skill(element=1),  # 火
        )
        assert result.effectiveness == 2.0
        assert "拔群" in result.effectiveness_label

    def test_effectiveness_resisted(self, calc):
        result = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[2]),  # 水
            _make_skill(element=1),  # 火
        )
        assert result.effectiveness == 0.5
        assert "不佳" in result.effectiveness_label

    def test_effectiveness_neutral(self, calc):
        result = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[0]),  # 普通
            _make_skill(element=1),
        )
        assert result.effectiveness == 1.0

    def test_dual_type_double_weakness(self, calc):
        # 电打 水/翼 = 2.0 * 2.0 = 4.0
        result = calc.calculate(
            _make_attacker(types=[4]),
            _make_defender(types=[2, 9]),  # 水/翼
            _make_skill(element=4),  # 电
        )
        assert result.effectiveness == 4.0

    def test_can_ko_true(self, calc):
        result = calc.calculate(
            _make_attacker(atk=9999),
            _make_defender(current_hp=1, max_hp=1),
            _make_skill(power=200),
        )
        assert result.can_ko is True

    def test_can_ko_false(self, calc):
        result = calc.calculate(
            _make_attacker(atk=10),
            _make_defender(current_hp=9999, max_hp=9999),
            _make_skill(power=10),
        )
        assert result.can_ko is False

    def test_non_attack_power_zero_returns_none(self, calc):
        attacker = _make_attacker()
        defender = _make_defender()
        skill = _make_skill(power=0)
        assert calc.calculate(attacker, defender, skill) is None

    def test_non_attack_damage_type_1_returns_none(self, calc):
        attacker = _make_attacker()
        defender = _make_defender()
        skill = _make_skill(dam_type=1)
        assert calc.calculate(attacker, defender, skill) is None

    def test_energy_warning(self, calc):
        attacker = _make_attacker(energy=1)
        result = calc.calculate(
            attacker,
            _make_defender(),
            _make_skill(energy_cost=[5]),
        )
        assert result is not None
        assert any("能量不足" in w for w in result.warnings)

    def test_no_energy_warning_when_sufficient(self, calc):
        attacker = _make_attacker(energy=10)
        result = calc.calculate(
            attacker,
            _make_defender(),
            _make_skill(energy_cost=[3]),
        )
        assert result is not None
        assert not any("能量不足" in w for w in result.warnings)

    def test_confidence_high_with_full_stats(self, calc):
        result = calc.calculate(
            _make_attacker(),
            _make_defender(),
            _make_skill(),
        )
        assert result.confidence == "high"

    def test_no_stats_returns_none(self, calc):
        """无攻防数据时不再返回不可靠的估算，而是返回 None。"""
        attacker = {"types": [1], "max_hp": 300, "current_hp": 300, "name": "不存在的宠物名xyz"}
        defender = {"types": [2], "max_hp": 350, "current_hp": 350}
        result = calc.calculate(attacker, defender, _make_skill())
        assert result is None

    def test_pct_hp_range(self, calc):
        result = calc.calculate(
            _make_attacker(),
            _make_defender(max_hp=1000, current_hp=1000),
            _make_skill(power=100),
        )
        assert result.pct_hp_range[0] > 0
        assert result.pct_hp_range[1] >= result.pct_hp_range[0]

    def test_damage_result_fields(self, calc):
        result = calc.calculate(
            _make_attacker(),
            _make_defender(),
            _make_skill(),
        )
        assert isinstance(result, DamageResult)
        assert result.skill_id == 7700001
        assert result.skill_name == "火焰冲击"
        assert result.power == 80
        assert result.skill_element == 1
        assert isinstance(result.min_damage, int)
        assert isinstance(result.max_damage, int)
        assert result.min_damage >= 1
        assert result.max_damage >= result.min_damage

    def test_to_dict(self, calc):
        result = calc.calculate(
            _make_attacker(),
            _make_defender(),
            _make_skill(),
        )
        d = result.to_dict()
        assert "skill_id" in d
        assert "min_damage" in d
        assert "max_damage" in d
        assert isinstance(d["pct_hp_range"], (list, tuple))


# ---------------------------------------------------------------------------
# TestDamageRange — 随机因子范围验证
# ---------------------------------------------------------------------------


class TestDamageRange:
    def test_random_factor_range(self, calc):
        # 验证 min/max 符合 217/255 ~ 255/255 的范围
        result = calc.calculate(
            _make_attacker(),
            _make_defender(),
            _make_skill(),
        )
        # 基础伤害 × effectiveness × STAB × (217/255 to 1.0)
        base = DamageCalculator._base_damage(100, 80, 200, 150)
        eff = 0.5  # 火打水
        stab = 1.5  # 火系宠物用火系技能
        max_expected = int(base * eff * stab * 1.0)
        min_expected = int(base * eff * stab * 217 / 255)
        assert result.max_damage == max(1, max_expected)
        assert result.min_damage == max(1, min_expected)
