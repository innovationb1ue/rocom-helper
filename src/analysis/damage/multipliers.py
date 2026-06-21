"""伤害最终倍率解析。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.analysis.damage.hook_pipeline import HookStage
from src.data.loader import get_weather_damage_mult

RunHooks = Callable[[HookStage, Dict[str, Any]], Dict[str, Any]]
GetMultiplier = Callable[[int, List[int]], float]
EffectivenessLabel = Callable[[float], str]

STAB_MULTIPLIER = 1.5


@dataclass
class DamageMultiplierInput:
    base_damage: float
    skill_element: int
    attacker: Dict[str, Any]
    defender: Dict[str, Any]
    skill_meta: Dict[str, Any]
    weather: Optional[Dict[str, Any]]
    server_runtime: Optional[Dict[str, Any]] = None


@dataclass
class DamageMultiplierResult:
    damage: int
    effectiveness: float
    stab_mult: float
    weather_mult: float
    power_mult: float
    effectiveness_label: str
    is_stab: bool

    def as_legacy_tuple(self) -> tuple[int, float, float, float, float, str, bool]:
        return (
            self.damage,
            self.effectiveness,
            self.stab_mult,
            self.weather_mult,
            self.power_mult,
            self.effectiveness_label,
            self.is_stab,
        )


def apply_damage_multipliers(
    data: DamageMultiplierInput,
    *,
    get_multiplier: GetMultiplier,
    get_effectiveness_label: EffectivenessLabel,
    run_hooks: RunHooks,
) -> DamageMultiplierResult:
    """应用属性克制、STAB、天气、pre_final hook 和服务端倍率。"""
    server_runtime = data.server_runtime if data.server_runtime is not None else {}
    local_effectiveness = get_multiplier(data.skill_element, data.defender.get("types", []))
    server_effectiveness = server_runtime.get("effectiveness")
    display_effectiveness = (
        server_effectiveness if server_effectiveness is not None else local_effectiveness
    )
    calc_effectiveness = _formula_effectiveness(display_effectiveness, server_runtime)
    server_runtime["local_effectiveness"] = local_effectiveness
    server_runtime["display_effectiveness"] = display_effectiveness
    server_runtime["calc_effectiveness"] = calc_effectiveness
    effectiveness_label = get_effectiveness_label(display_effectiveness)

    is_stab = data.skill_element in data.attacker.get("types", [])
    stab_mult = STAB_MULTIPLIER if is_stab else 1.0
    weather_mult = get_weather_damage_mult(data.weather, data.skill_element)
    power_mult = 1.0

    ctx = run_hooks("pre_final", {
        "base_damage": data.base_damage,
        "effectiveness": calc_effectiveness,
        "stab_mult": stab_mult,
        "weather_mult": weather_mult,
        "power_mult": power_mult,
        "skill_meta": data.skill_meta,
        "attacker": data.attacker,
        "defender": data.defender,
    })
    base_damage = ctx["base_damage"]
    calc_effectiveness = ctx["effectiveness"]
    stab_mult = ctx["stab_mult"]
    weather_mult = ctx.get("weather_mult", weather_mult)
    power_mult = ctx.get("power_mult", power_mult)
    if server_runtime.get("server_power_applied"):
        power_mult *= float(server_runtime.get("server_power_multiplier") or 1.0)
    if server_runtime.get("effectiveness_source") != "server_restraint_types":
        display_effectiveness = calc_effectiveness
        effectiveness_label = get_effectiveness_label(display_effectiveness)
    server_runtime["display_effectiveness"] = display_effectiveness
    server_runtime["calc_effectiveness"] = calc_effectiveness

    damage = max(1, int(base_damage * calc_effectiveness * stab_mult * weather_mult * power_mult))
    return DamageMultiplierResult(
        damage=damage,
        effectiveness=display_effectiveness,
        stab_mult=stab_mult,
        weather_mult=weather_mult,
        power_mult=power_mult,
        effectiveness_label=effectiveness_label,
        is_stab=is_stab,
    )


def _formula_effectiveness(display_effectiveness: float, server_runtime: Dict[str, Any]) -> float:
    # damage_params 已按目标给出威力参数，进入公式后不再重复乘克制。
    if (
        server_runtime.get("power_source") == "server_damage_params"
        and server_runtime.get("power_used_in_formula")
    ):
        return 1.0
    return display_effectiveness
