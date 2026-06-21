"""伤害最终结果构造测试。"""
from __future__ import annotations

from src.analysis.damage.finalize import (
    DamageFinalizeInput,
    finalize_damage_result,
    reflect_buff_applied,
)


def _input(**overrides) -> DamageFinalizeInput:
    data = {
        "dmg": 40,
        "power": 80,
        "ability_level": 1.25,
        "effective_atk": 200,
        "effective_def": 100,
        "effectiveness": 2.0,
        "stab_mult": 1.5,
        "weather_mult": 1.0,
        "power_mult": 1.0,
        "skill_meta": {
            "id": 900001,
            "name": "测试火焰",
            "damage_type": 2,
            "dam_para": [80],
            "energy_cost": [3],
        },
        "skill_element": 1,
        "attacker": {"energy": 2, "buffs": []},
        "defender": {"current_hp": 90, "max_hp": 200, "buffs": []},
        "damage_type": 2,
        "eff_label": "效果拔群",
        "is_stab": True,
        "confidence": "high",
        "warnings": [],
        "stat_sources": {"attack": "total", "defense": "total"},
        "runtime_skill": {},
        "server_runtime": {"formula_power_source": "skill_config"},
        "final_power": 80,
        "special_fixed_light_skills": {},
    }
    data.update(overrides)
    return DamageFinalizeInput(**data)


def test_finalize_damage_result_builds_compatible_damage_result():
    result = finalize_damage_result(
        _input(),
        run_hooks=lambda stage, ctx: ctx,
        type_name=lambda element: "火" if element == 1 else "?",
    )

    assert result.skill_name == "测试火焰"
    assert result.expected_damage == 40
    assert result.total_damage == 40
    assert result.pct_hp == 0.2
    assert result.can_ko is False
    assert result.energy_cost == 3
    assert result.warnings == ["能量不足 (需要3, 当前2)"]
    assert result.damage_breakdown["base_power"] == 80
    assert result.damage_breakdown["ability_level"] == 1.25
    assert result.damage_breakdown["stat_sources"] == {"attack": "total", "defense": "total"}


def test_finalize_damage_result_applies_post_calc_hook_hit_count():
    def run_hooks(stage, ctx):
        assert stage == "post_calc"
        return {**ctx, "min_damage": 30, "hit_count": 3}

    result = finalize_damage_result(
        _input(defender={"current_hp": 90, "max_hp": 300, "buffs": []}),
        run_hooks=run_hooks,
        type_name=lambda element: "火",
    )

    assert result.expected_damage == 30
    assert result.hit_count == 3
    assert result.total_damage == 90
    assert result.can_ko is True
    assert result.pct_hp == 0.3
    assert result.damage_breakdown["hit_count"] == 3


def test_finalize_damage_result_marks_special_rule_placeholder():
    result = finalize_damage_result(
        _input(special_fixed_light_skills={900001: "fixed_light"}),
        run_hooks=lambda stage, ctx: ctx,
        type_name=lambda element: "火",
    )

    assert result.damage_breakdown["special_damage_rule"] == {
        "mode": "fixed_light",
        "element": 1,
        "source": "config_missing",
        "applied": False,
    }


def test_reflect_buff_applied_requires_real_derived_modifiers():
    assert reflect_buff_applied([{"id": 20890020, "derived_buffs": [{"id": 1}]}]) is True
    assert reflect_buff_applied([{"id": 20890020}]) is False
    assert reflect_buff_applied([{"id": 1, "derived_buffs": [{"id": 1}]}]) is False
