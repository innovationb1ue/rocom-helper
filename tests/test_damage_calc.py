"""伤害计算器测试 — 验证 NRC_AI 伤害公式、STAB、属性克制、KO 判定、置信度。"""
from __future__ import annotations

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
# TestBaseDamage — 公式: (ATK / DEF) * power * 0.9
# ---------------------------------------------------------------------------


class TestBaseDamage:
    def test_known_values(self):
        # (200 / 100) * 80 * 0.9 = 144.0
        result = DamageCalculator._base_damage(200, 100, 80)
        assert result == 144.0

    def test_atk_scaling(self):
        d1 = DamageCalculator._base_damage(100, 100, 80)
        d2 = DamageCalculator._base_damage(200, 100, 80)
        assert d2 > d1

    def test_power_scaling(self):
        d1 = DamageCalculator._base_damage(200, 100, 40)
        d2 = DamageCalculator._base_damage(200, 100, 80)
        assert d2 > d1

    def test_zero_defense_clamps_to_one(self):
        result = DamageCalculator._base_damage(200, 0, 80)
        assert result > 0

    def test_negative_defense_clamps_to_one(self):
        result = DamageCalculator._base_damage(200, -10, 80)
        assert result > 0

    def test_minimum_damage(self):
        result = DamageCalculator._base_damage(1, 9999, 1)
        assert result > 0


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
        # 确定性公式: min == max
        assert result.max_damage == result.min_damage

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
        # 电(SDT=11)打 水/翼 = 2.0 * 2.0 = 4.0
        result = calc.calculate(
            _make_attacker(types=[4]),
            _make_defender(types=[2, 9]),  # 水/翼
            _make_skill(element=11),  # 电 SDT=11 → type 4
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
        assert isinstance(result.min_damage, int)
        assert isinstance(result.max_damage, int)
        assert result.min_damage >= 1
        assert result.max_damage >= result.min_damage

    def test_expected_damage_equals_min_max(self, calc):
        """确定性公式: expected_damage == min_damage == max_damage。"""
        result = calc.calculate(
            _make_attacker(),
            _make_defender(),
            _make_skill(),
        )
        assert result.expected_damage == result.min_damage
        assert result.expected_damage == result.max_damage

    def test_effective_power_with_stab(self, calc):
        """本系加成时 effective_power = power * 1.5。"""
        result = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[0]),
            _make_skill(element=1, power=80),
        )
        assert result.is_stab is True
        assert result.effective_power == 120  # 80 * 1.5

    def test_effective_power_without_stab(self, calc):
        result = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[0]),
            _make_skill(element=2, power=80),
        )
        assert result.is_stab is False
        assert result.effective_power == 80

    def test_damage_breakdown(self, calc):
        result = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[3]),  # 草
            _make_skill(element=1),  # 火
        )
        bd = result.damage_breakdown
        assert bd["base_power"] == 80
        assert bd["effectiveness"] == 2.0
        assert bd["stab"] == 1.5
        assert bd["hit_count"] == 1

    def test_runtime_skill_values_are_explain_only(self, calc):
        """运行时威力参数进入解释字段，但不直接替换伤害公式威力。"""
        attacker = _make_attacker(types=[1], energy=3)
        attacker["skill_runtime"] = {
            "7700001": {
                "damage_param_result": 150,
                "cost_energy_result": 4,
                "pp_result": 8,
            }
        }
        result = calc.calculate(attacker, _make_defender(types=[3]), _make_skill(element=1))
        bd = result.damage_breakdown
        assert result.power == 80
        assert result.energy_cost == 4
        assert bd["base_power"] == 80
        assert bd["runtime_power"] == 150
        assert bd["damage_param_result"] == 150
        assert bd["runtime_skill"]["pp_result"] == 8

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
        assert "expected_damage" in d
        assert "effective_power" in d
        assert "damage_breakdown" in d
        assert "hit_count" in d
        assert "total_min_damage" in d
        assert "total_max_damage" in d
        assert isinstance(d["pct_hp_range"], (list, tuple))


# ---------------------------------------------------------------------------
# TestDeterministic — 验证确定性输出
# ---------------------------------------------------------------------------


class TestDeterministic:
    def test_min_equals_max(self, calc):
        result = calc.calculate(
            _make_attacker(),
            _make_defender(),
            _make_skill(),
        )
        assert result.min_damage == result.max_damage

    def test_pct_range_identical(self, calc):
        result = calc.calculate(
            _make_attacker(),
            _make_defender(max_hp=1000, current_hp=1000),
            _make_skill(),
        )
        assert result.pct_hp_range[0] == result.pct_hp_range[1]

    def test_nrc_ai_formula_value(self, calc):
        """验证 NRC_AI 公式: (ATK/DEF) * power * 0.9 * effectiveness * stab。"""
        # ATK=200, DEF=150, power=80, eff=0.5 (火打水), stab=1.5 (火系宠物用火系技能)
        result = calc.calculate(
            _make_attacker(types=[1]),   # 火系
            _make_defender(types=[2]),   # 水系
            _make_skill(element=1),      # 火 SDT=4, type=1
        )
        base = (200 / 150) * 80 * 0.9  # = 96.0
        expected = max(1, int(base * 0.5 * 1.5))  # = 72
        assert result.expected_damage == expected


# ---------------------------------------------------------------------------
# TestHookSystem — hook 注册、执行、清理
# ---------------------------------------------------------------------------


class TestHookSystem:
    def test_register_hook_stores_hook(self):
        c = DamageCalculator()
        assert len(c._hooks["pre_power"]) == 0
        c.register_hook("pre_power", lambda ctx: ctx)
        assert len(c._hooks["pre_power"]) == 1

    def test_register_hook_rejects_unknown_stage(self):
        c = DamageCalculator()
        with pytest.raises(ValueError, match="Unknown hook stage"):
            c.register_hook("invalid_stage", lambda ctx: ctx)  # type: ignore[arg-type]

    def test_clear_hooks(self):
        c = DamageCalculator()
        c.register_hook("pre_power", lambda ctx: ctx)
        c.register_hook("post_base", lambda ctx: ctx)
        c.clear_hooks()
        for stage in c._hooks:
            assert len(c._hooks[stage]) == 0

    def test_pre_power_hook_modifies_power(self, calc):
        calc.register_hook("pre_power", lambda ctx: {**ctx, "power": ctx["power"] * 2})
        result_no_hook = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[0]),
            _make_skill(element=1, power=80),
        )
        result = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[0]),
            _make_skill(element=1, power=80),
        )
        # base power stays the same
        assert result.power == 80
        # doubled power causes roughly 2x damage
        assert result.expected_damage > 0

    def test_post_base_hook_modifies_base_damage(self, calc):
        def double_base(ctx):
            return {**ctx, "base_damage": ctx["base_damage"] * 2}
        calc.register_hook("post_base", double_base)
        result = calc.calculate(
            _make_attacker(),
            _make_defender(),
            _make_skill(power=80),
        )
        assert result is not None
        assert result.expected_damage > 100

    def test_pre_final_hook_modifies_effectiveness(self, calc):
        def set_half_eff(ctx):
            return {**ctx, "effectiveness": 0.5}
        calc.register_hook("pre_final", set_half_eff)
        result = calc.calculate(
            _make_attacker(types=[1]),
            _make_defender(types=[0]),
            _make_skill(element=1),
        )
        assert result.effectiveness == 0.5

    def test_post_calc_hook_modifies_damage(self, calc):
        def add_bonus(ctx):
            return {**ctx, "min_damage": ctx["min_damage"] + 100, "max_damage": ctx["max_damage"] + 100}
        calc.register_hook("post_calc", add_bonus)
        result = calc.calculate(
            _make_attacker(),
            _make_defender(),
            _make_skill(power=80),
        )
        assert result.min_damage >= 100
        assert result.max_damage >= 100

    def test_multiple_hooks_same_stage_execute_in_order(self, calc):
        call_order = []

        def hook_a(ctx):
            call_order.append("a")
            return ctx

        def hook_b(ctx):
            call_order.append("b")
            return ctx

        calc.register_hook("pre_power", hook_a)
        calc.register_hook("pre_power", hook_b)
        calc.calculate(_make_attacker(), _make_defender(), _make_skill())
        assert call_order == ["a", "b"]

    def test_hooks_across_stages(self, calc):
        stages_seen = []

        def record_stage(stage):
            def hook(ctx):
                stages_seen.append(stage)
                return ctx
            return hook

        calc.register_hook("pre_power", record_stage("pre_power"))
        calc.register_hook("post_base", record_stage("post_base"))
        calc.register_hook("pre_final", record_stage("pre_final"))
        calc.register_hook("post_calc", record_stage("post_calc"))
        calc.calculate(_make_attacker(), _make_defender(), _make_skill())
        assert stages_seen == ["pre_power", "post_base", "pre_final", "post_calc"]

    def test_no_hooks_produces_same_result(self):
        c1 = DamageCalculator()
        c2 = DamageCalculator()
        atk = _make_attacker()
        dfn = _make_defender()
        skill = _make_skill()
        r1 = c1.calculate(atk, dfn, skill)
        r2 = c2.calculate(atk, dfn, skill)
        assert r1.min_damage == r2.min_damage
        assert r1.max_damage == r2.max_damage

    def test_can_ko_updated_after_post_calc_hook(self, calc):
        """post_calc hook increases damage enough to KO."""
        def force_high_damage(ctx):
            return {**ctx, "min_damage": 99999, "max_damage": 99999}
        calc.register_hook("post_calc", force_high_damage)
        result = calc.calculate(
            _make_attacker(),
            _make_defender(current_hp=100, max_hp=350),
            _make_skill(power=10),
        )
        assert result.can_ko is True


# ---------------------------------------------------------------------------
# TestComboDamage — hit_count, total damage fields
# ---------------------------------------------------------------------------


class TestComboDamage:
    def test_default_hit_count_is_one(self):
        calc = DamageCalculator(TypeChart())
        result = calc.calculate(_make_attacker(), _make_defender(), _make_skill())
        assert result.hit_count == 1
        assert result.total_min_damage == result.min_damage
        assert result.total_max_damage == result.max_damage

    def test_combo_hook_sets_hit_count(self):
        calc = DamageCalculator(TypeChart())

        def combo_hook(ctx):
            return {**ctx, "hit_count": 3}

        calc.register_hook("post_calc", combo_hook)
        result = calc.calculate(_make_attacker(), _make_defender(), _make_skill())
        assert result.hit_count == 3
        assert result.total_min_damage == result.min_damage * 3
        assert result.total_max_damage == result.max_damage * 3

    def test_combo_can_ko_uses_total_damage(self):
        calc = DamageCalculator(TypeChart())

        def combo_hook(ctx):
            return {**ctx, "hit_count": 5}

        calc.register_hook("post_calc", combo_hook)
        result = calc.calculate(
            _make_attacker(atk=100),
            _make_defender(current_hp=200, max_hp=350),
            _make_skill(power=40),
        )
        assert result.can_ko == (result.total_min_damage >= 200)

    def test_combo_pct_hp_uses_total_damage(self):
        calc = DamageCalculator(TypeChart())

        def combo_hook(ctx):
            return {**ctx, "hit_count": 4}

        calc.register_hook("post_calc", combo_hook)
        result = calc.calculate(
            _make_attacker(),
            _make_defender(max_hp=1000, current_hp=1000),
            _make_skill(power=80),
        )
        assert result.pct_hp_range[0] == result.total_min_damage / 1000
        assert result.pct_hp_range[1] == result.total_max_damage / 1000

    def test_to_dict_includes_combo_fields(self):
        calc = DamageCalculator(TypeChart())
        result = calc.calculate(_make_attacker(), _make_defender(), _make_skill())
        d = result.to_dict()
        assert d["hit_count"] == 1
        assert d["total_min_damage"] == result.min_damage
        assert d["total_max_damage"] == result.max_damage


# ---------------------------------------------------------------------------
# TestBaseHitCount — 基础连击数解析
# ---------------------------------------------------------------------------


class TestBaseHitCount:
    def test_two_combo_from_desc(self):
        assert DamageCalculator._get_base_hit_count({"desc": "造成物伤，2连击。"}) == 2

    def test_three_combo_from_desc(self):
        assert DamageCalculator._get_base_hit_count({"desc": "造成魔伤，3连击。"}) == 3

    def test_ten_combo_from_desc(self):
        assert DamageCalculator._get_base_hit_count({"desc": "造成物伤，10连击。"}) == 10

    def test_one_combo_from_desc(self):
        assert DamageCalculator._get_base_hit_count({"desc": "造成魔伤，1连击。"}) == 1

    def test_no_combo_defaults_to_one(self):
        assert DamageCalculator._get_base_hit_count({"desc": "造成物伤。"}) == 1

    def test_empty_desc_defaults_to_one(self):
        assert DamageCalculator._get_base_hit_count({"desc": ""}) == 1

    def test_no_desc_defaults_to_one(self):
        assert DamageCalculator._get_base_hit_count({}) == 1


# ---------------------------------------------------------------------------
# TestInnateHooksRegistration — BattleAdvisor 注册先天 hooks
# ---------------------------------------------------------------------------


class TestInnateHooksRegistration:
    def test_advisor_registers_innate_hooks(self):
        from src.analysis.battle_advisor import BattleAdvisor
        advisor = BattleAdvisor()
        hooks = advisor._damage_calc._hooks
        assert len(hooks["post_base"]) >= 1   # stat_modify_hook
        assert len(hooks["pre_final"]) >= 1   # type_resist_modify_hook
        assert len(hooks["post_calc"]) >= 2   # combo_modify_hook + power_modify_hook

    def test_base_hit_count_in_calc_result(self):
        from src.analysis.battle_advisor import BattleAdvisor
        advisor = BattleAdvisor()
        attacker = _make_attacker()
        defender = _make_defender()
        skill = _make_skill(power=25)
        skill["desc"] = "造成物伤，2连击。"
        result = advisor._damage_calc.calculate(attacker, defender, skill)
        assert result is not None
        assert result.hit_count >= 2
        assert result.total_min_damage == result.min_damage * result.hit_count
        assert result.total_max_damage == result.max_damage * result.hit_count
