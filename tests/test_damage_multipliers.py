"""伤害最终倍率解析测试。"""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.damage.multipliers import (
    DamageMultiplierInput,
    apply_damage_multipliers,
)


def _label(multiplier: float) -> str:
    return {
        0.5: "效果不佳",
        1.0: "普通",
        2.0: "效果拔群",
    }.get(multiplier, f"x{multiplier}")


def _identity_hook(stage: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    assert stage == "pre_final"
    return ctx


def test_apply_damage_multipliers_uses_local_effectiveness_and_stab():
    result = apply_damage_multipliers(
        DamageMultiplierInput(
            base_damage=100,
            skill_element=1,
            attacker={"types": [1]},
            defender={"types": [3]},
            skill_meta={"name": "火焰冲击"},
            weather=None,
            server_runtime={},
        ),
        get_multiplier=lambda attack_type, defend_types: 2.0,
        get_effectiveness_label=_label,
        run_hooks=_identity_hook,
    )

    assert result.damage == 300
    assert result.effectiveness == 2.0
    assert result.effectiveness_label == "效果拔群"
    assert result.stab_mult == 1.5
    assert result.weather_mult == 1.0
    assert result.power_mult == 1.0
    assert result.is_stab is True


def test_server_restraint_stays_displayed_when_formula_skips_effectiveness():
    server_runtime = {
        "effectiveness": 2.0,
        "effectiveness_source": "server_restraint_types",
        "power_source": "server_damage_params",
        "power_used_in_formula": True,
        "server_power_applied": True,
        "server_power_multiplier": 2.0,
    }

    result = apply_damage_multipliers(
        DamageMultiplierInput(
            base_damage=100,
            skill_element=1,
            attacker={"types": []},
            defender={"types": [3]},
            skill_meta={"name": "火焰冲击"},
            weather=None,
            server_runtime=server_runtime,
        ),
        get_multiplier=lambda attack_type, defend_types: 0.5,
        get_effectiveness_label=_label,
        run_hooks=_identity_hook,
    )

    assert result.damage == 200
    assert result.effectiveness == 2.0
    assert result.effectiveness_label == "效果拔群"
    assert result.power_mult == 2.0
    assert server_runtime["local_effectiveness"] == 0.5
    assert server_runtime["calc_effectiveness"] == 1.0
    assert server_runtime["display_effectiveness"] == 2.0


def test_pre_final_hook_can_update_formula_and_display_effectiveness():
    def hook(stage: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        assert stage == "pre_final"
        return {
            **ctx,
            "base_damage": 50,
            "effectiveness": 0.5,
            "stab_mult": 1.0,
            "weather_mult": 2.0,
            "power_mult": 3.0,
        }

    server_runtime: Dict[str, Any] = {}
    result = apply_damage_multipliers(
        DamageMultiplierInput(
            base_damage=100,
            skill_element=1,
            attacker={"types": [1]},
            defender={"types": [3]},
            skill_meta={"name": "火焰冲击"},
            weather=None,
            server_runtime=server_runtime,
        ),
        get_multiplier=lambda attack_type, defend_types: 2.0,
        get_effectiveness_label=_label,
        run_hooks=hook,
    )

    assert result.damage == 150
    assert result.effectiveness == 0.5
    assert result.effectiveness_label == "效果不佳"
    assert result.stab_mult == 1.0
    assert result.weather_mult == 2.0
    assert result.power_mult == 3.0
    assert server_runtime["calc_effectiveness"] == 0.5
    assert server_runtime["display_effectiveness"] == 0.5
