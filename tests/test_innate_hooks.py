"""先天技能 hook 测试 — 验证 combo/stat/type/power 四种修正效果。"""
from __future__ import annotations

import pytest

from src.analysis.damage_calc import DamageCalculator
from src.analysis.innate_hooks import (
    combo_modify_hook,
    power_modify_hook,
    register_innate_hooks,
    stat_modify_hook,
    type_resist_modify_hook,
)
from src.game.type_chart import TypeChart


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_attacker(
    types=None,
    atk=200,
    spa=180,
    level=100,
    max_hp=300,
    current_hp=300,
    energy=10,
    combo_bonus=0,
    base_id=None,
    poison_stacks=0,
    buffs=None,
    first_strike=False,
):
    types = types or [1]
    pet = {
        "types": types,
        "level": level,
        "max_hp": max_hp,
        "current_hp": current_hp,
        "energy": energy,
        "combo_bonus": combo_bonus,
        "poison_stacks": poison_stacks,
        "first_strike": first_strike,
        "stats": [
            {"name": "ATK", "total": atk},
            {"name": "SPA", "total": spa},
            {"name": "DEF", "total": 150},
            {"name": "SPD", "total": 150},
        ],
    }
    if base_id is not None:
        pet["base_id"] = base_id
    if buffs is not None:
        pet["buffs"] = buffs
    return pet


def _make_defender(types=None, def_=150, spd=150, max_hp=350, current_hp=350, poison_stacks=0):
    types = types or [2]
    return {
        "types": types,
        "max_hp": max_hp,
        "current_hp": current_hp,
        "poison_stacks": poison_stacks,
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
# TestComboModifyHook
# ---------------------------------------------------------------------------


class TestComboModifyHook:
    def test_no_combo_bonus_no_change(self):
        ctx = {
            "min_damage": 50,
            "max_damage": 60,
            "hit_count": 2,
            "attacker": _make_attacker(combo_bonus=0),
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = combo_modify_hook(ctx)
        assert result["min_damage"] == 50
        assert result["max_damage"] == 60
        assert result["hit_count"] == 2  # base unchanged

    def test_combo_always_adds_hits(self):
        """连击+1 (buff 20450020): always +1 hit — 持久 buff 在 buff 列表中被 hook 扫描到"""
        attacker = _make_attacker(
            combo_bonus=3,
            buffs=[{"id": 20450020}],  # 持久 buff，hook 直接扫描
        )
        ctx = {
            "min_damage": 50,
            "max_damage": 60,
            "hit_count": 1,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = combo_modify_hook(ctx)
        assert result["hit_count"] == 5  # (1 base + 3 combo + 0 acc) * 1 + 1 bonus
        assert result["min_damage"] == 50
        assert result["max_damage"] == 60

    def test_combo_multiplier(self):
        """连击翻倍 (buff 20450030): multiplier=2"""
        attacker = _make_attacker(
            combo_bonus=3,
            buffs=[{"id": 20450030}],
        )
        ctx = {
            "min_damage": 50,
            "max_damage": 60,
            "hit_count": 1,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = combo_modify_hook(ctx)
        assert result["hit_count"] == 8  # (1 + 3) * 2
        assert result["min_damage"] == 50
        assert result["max_damage"] == 60

    def test_combo_poison_stacks(self):
        """毒连击 (buff 29990910): per_poison_stack +1"""
        attacker = _make_attacker(
            combo_bonus=2,
            buffs=[{"id": 29990910}],
        )
        defender = _make_defender(poison_stacks=3)
        ctx = {
            "min_damage": 50,
            "max_damage": 60,
            "hit_count": 2,
            "attacker": attacker,
            "defender": defender,
            "skill_meta": _make_skill(),
        }
        result = combo_modify_hook(ctx)
        assert result["hit_count"] == 7  # (2 base + 2 combo) * 1 + 3 poison
        assert result["min_damage"] == 50

    def test_combo_element_trigger(self):
        """翼系连击 (buff 20350300): skill_element_used, element=14"""
        attacker = _make_attacker(
            combo_bonus=2,
            buffs=[{"id": 20350300}],
        )
        # Using wing-type skill (element 14)
        ctx_match = {
            "min_damage": 50,
            "max_damage": 60,
            "hit_count": 2,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(element=14),
        }
        result = combo_modify_hook(ctx_match)
        assert result["hit_count"] == 5  # (2 + 2) * 1 + 1 element bonus

        # Using non-wing skill (element 1)
        ctx_no_match = {
            "min_damage": 50,
            "max_damage": 60,
            "hit_count": 2,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(element=1),
        }
        result = combo_modify_hook(ctx_no_match)
        assert result["hit_count"] == 4  # (2 + 2) * 1, no element bonus

    def test_combo_multiple_innate_skills(self):
        """Multiple combo innate skills stack additively — persistent buffs scanned by hook."""
        attacker = _make_attacker(
            combo_bonus=2,
            buffs=[{"id": 20450020}, {"id": 20450050}],  # 连击+1 + 通用连击+1 (persistent)
        )
        ctx = {
            "min_damage": 50,
            "max_damage": 60,
            "hit_count": 1,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = combo_modify_hook(ctx)
        assert result["hit_count"] == 5  # (1 + 2 + 0 acc) * 1 + 1 + 1

    def test_no_innate_buff_uses_base_combo(self):
        """Combo bonus but no innate skills → hit_count = base + combo_bonus."""
        attacker = _make_attacker(combo_bonus=3, buffs=[])
        ctx = {
            "min_damage": 50,
            "max_damage": 60,
            "hit_count": 2,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = combo_modify_hook(ctx)
        assert result["hit_count"] == 5  # 2 base + 3 combo, no multiplier
        assert result["min_damage"] == 50

    def test_non_innate_buff_ignored(self):
        """Buffs that are not innate skills should be ignored."""
        attacker = _make_attacker(
            combo_bonus=2,
            buffs=[{"id": 99999999}],  # Not an innate skill buff
        )
        ctx = {
            "min_damage": 50,
            "max_damage": 60,
            "hit_count": 2,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = combo_modify_hook(ctx)
        assert result["hit_count"] == 4  # 2 base + 2 combo

    def test_passive_talent_via_pet_mapping(self):
        """被动天赋通过 base_id 从 innate_skills.json pets 映射发现（无需 buff）。"""
        # 厉毒修萝 base_id=3420，pets 映射中有 29990910（毒连击/侵蚀）
        attacker = _make_attacker(
            combo_bonus=0,
            base_id=3420,
            buffs=[],  # 无 buff，天赋通过 pet mapping 发现
        )
        defender = _make_defender(poison_stacks=5)
        ctx = {
            "min_damage": 50,
            "max_damage": 60,
            "hit_count": 2,
            "attacker": attacker,
            "defender": defender,
            "skill_meta": _make_skill(),
        }
        result = combo_modify_hook(ctx)
        # (2 base + 0 combo) * 1 + 5 poison = 7
        assert result["hit_count"] == 7

    def test_passive_talent_and_buff_stack(self):
        """被动天赋 + buff 扫描的结果应该叠加（不重复）。"""
        # base_id=3420 提供 29990910，buff 20450020 是另一个 combo_modify
        attacker = _make_attacker(
            combo_bonus=1,
            base_id=3420,
            buffs=[{"id": 20450020}],  # 连击+1（持久 buff）
        )
        defender = _make_defender(poison_stacks=3)
        ctx = {
            "min_damage": 50,
            "max_damage": 60,
            "hit_count": 2,
            "attacker": attacker,
            "defender": defender,
            "skill_meta": _make_skill(),
        }
        result = combo_modify_hook(ctx)
        # (2 + 1) * 1 + 3 poison + 1 always = 7
        assert result["hit_count"] == 7


# ---------------------------------------------------------------------------
# TestStatModifyHook
# ---------------------------------------------------------------------------


class TestStatModifyHook:
    def test_hp_below_threshold(self):
        """临界防御 (buff 20410080): HP<50% → ATK+40%"""
        attacker = _make_attacker(
            max_hp=300,
            current_hp=100,  # 33% < 50%
            buffs=[{"id": 20410080}],
        )
        ctx = {
            "base_damage": 100,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = stat_modify_hook(ctx)
        assert result["base_damage"] == 140  # 100 * 1.4

    def test_hp_above_threshold_no_change(self):
        """HP above threshold → no modification."""
        attacker = _make_attacker(
            max_hp=300,
            current_hp=200,  # 67% > 50%
            buffs=[{"id": 20410080}],
        )
        ctx = {
            "base_damage": 100,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = stat_modify_hook(ctx)
        assert result["base_damage"] == 100

    def test_hp_exactly_at_threshold(self):
        """HP exactly at threshold → applies (<=)."""
        attacker = _make_attacker(
            max_hp=300,
            current_hp=150,  # exactly 50%
            buffs=[{"id": 20410080}],
        )
        ctx = {
            "base_damage": 100,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = stat_modify_hook(ctx)
        assert result["base_damage"] == 140

    def test_no_stat_modify_buff(self):
        """No stat_modify innate → no change."""
        attacker = _make_attacker(buffs=[{"id": 20450020}])  # combo_modify, not stat
        ctx = {
            "base_damage": 100,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = stat_modify_hook(ctx)
        assert result["base_damage"] == 100

    def test_no_buffs(self):
        """No buffs at all → no change."""
        attacker = _make_attacker(buffs=[])
        ctx = {
            "base_damage": 100,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = stat_modify_hook(ctx)
        assert result["base_damage"] == 100


# ---------------------------------------------------------------------------
# TestTypeResistModifyHook
# ---------------------------------------------------------------------------


class TestTypeResistModifyHook:
    def test_resisted_becomes_neutral(self):
        """无视抵抗 (buff 20420100): min_effectiveness=1.0 → 0.5 → 1.0"""
        attacker = _make_attacker(buffs=[{"id": 20420100}])
        ctx = {
            "effectiveness": 0.5,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = type_resist_modify_hook(ctx)
        assert result["effectiveness"] == 1.0

    def test_super_effective_unchanged(self):
        """Super effective (2.0) > min (1.0) → unchanged."""
        attacker = _make_attacker(buffs=[{"id": 20420100}])
        ctx = {
            "effectiveness": 2.0,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = type_resist_modify_hook(ctx)
        assert result["effectiveness"] == 2.0

    def test_neutral_unchanged(self):
        """Neutral (1.0) ≥ min (1.0) → unchanged."""
        attacker = _make_attacker(buffs=[{"id": 20420100}])
        ctx = {
            "effectiveness": 1.0,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = type_resist_modify_hook(ctx)
        assert result["effectiveness"] == 1.0

    def test_double_resisted_clamped(self):
        """Double resisted (0.25) → clamped to 1.0."""
        attacker = _make_attacker(buffs=[{"id": 20420100}])
        ctx = {
            "effectiveness": 0.25,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = type_resist_modify_hook(ctx)
        assert result["effectiveness"] == 1.0

    def test_no_type_resist_buff(self):
        """No type_resist_modify buff → no change."""
        attacker = _make_attacker(buffs=[{"id": 20450020}])
        ctx = {
            "effectiveness": 0.5,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = type_resist_modify_hook(ctx)
        assert result["effectiveness"] == 0.5


# ---------------------------------------------------------------------------
# TestPowerModifyHook
# ---------------------------------------------------------------------------


class TestPowerModifyHook:
    def test_first_strike_lifesteal(self):
        """先机虹吸 (buff 20430060): first_strike → 30% lifesteal"""
        attacker = _make_attacker(
            buffs=[{"id": 20430060}],
            first_strike=True,
        )
        ctx = {
            "min_damage": 80,
            "max_damage": 100,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = power_modify_hook(ctx)
        assert result.get("lifesteal_pct") == 30
        assert result.get("lifesteal_heal") == 30  # 100 * 30 / 100

    def test_not_first_strike_no_lifesteal(self):
        """first_strike=False → no lifesteal."""
        attacker = _make_attacker(
            buffs=[{"id": 20430060}],
            first_strike=False,
        )
        ctx = {
            "min_damage": 80,
            "max_damage": 100,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = power_modify_hook(ctx)
        assert "lifesteal_pct" not in result
        assert "lifesteal_heal" not in result

    def test_no_first_strike_flag(self):
        """No first_strike flag → no lifesteal."""
        attacker = _make_attacker(buffs=[{"id": 20430060}])
        ctx = {
            "min_damage": 80,
            "max_damage": 100,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = power_modify_hook(ctx)
        assert "lifesteal_pct" not in result

    def test_no_power_modify_buff(self):
        """No power_modify buff → no change."""
        attacker = _make_attacker(buffs=[{"id": 20450020}])
        ctx = {
            "min_damage": 80,
            "max_damage": 100,
            "attacker": attacker,
            "defender": _make_defender(),
            "skill_meta": _make_skill(),
        }
        result = power_modify_hook(ctx)
        assert "lifesteal_pct" not in result


# ---------------------------------------------------------------------------
# TestRegisterInnateHooks — 便捷注册
# ---------------------------------------------------------------------------


class TestRegisterInnateHooks:
    def test_registers_four_hooks(self):
        calc = DamageCalculator()
        register_innate_hooks(calc)
        assert stat_modify_hook in calc._hooks["post_base"]
        assert type_resist_modify_hook in calc._hooks["pre_final"]
        assert combo_modify_hook in calc._hooks["post_calc"]
        assert power_modify_hook in calc._hooks["post_calc"]

    def test_full_pipeline_with_innate_skills(self):
        """Integration: calculate damage with innate hooks active."""
        calc = DamageCalculator(TypeChart())
        register_innate_hooks(calc)

        # Attacker has 临界防御 (stat_modify) and 无视抵抗 (type_resist_modify)
        attacker = _make_attacker(
            types=[1],
            atk=300,
            buffs=[{"id": 20410080}, {"id": 20420100}],
            max_hp=300,
            current_hp=50,  # low HP → stat_modify triggers
        )
        defender = _make_defender(types=[2])  # water resists fire
        skill = _make_skill(element=1)  # fire vs water

        result = calc.calculate(attacker, defender, skill)
        assert result is not None
        # type_resist_modify should override 0.5 → 1.0
        assert result.effectiveness == 1.0
        # stat_modify should boost base damage by 40%
        # Compare against baseline (no innate) to verify boost
        calc2 = DamageCalculator(TypeChart())
        baseline = calc2.calculate(
            _make_attacker(types=[1], atk=300, max_hp=300, current_hp=50),
            defender,
            skill,
        )
        # With 40% boost + neutral effectiveness vs 0.5 effectiveness
        # Innate result should be notably higher
        assert result.max_damage > baseline.max_damage
