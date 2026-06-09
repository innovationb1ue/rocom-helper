"""DamageCalculator calculation phase methods.

The facade keeps these as private methods for compatibility, but the phase
implementation lives here so each stage can be tested without the public class
also carrying all formula/multiplier/finalization wiring.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.analysis.damage import combat_stats
from src.analysis.damage import formula as damage_formula
from src.analysis.damage import multipliers as damage_multipliers
from src.analysis.damage import server_runtime as damage_server_runtime
from src.analysis.damage.finalize import DamageFinalizeInput, finalize_damage_result
from src.analysis.damage.result import DamageResult

SPECIAL_FIXED_LIGHT_SKILLS: Dict[int, str] = {}


class DamageCalculationPhasesMixin:
    """Private calculation phases used by `DamageCalculator.calculate`."""

    def _apply_server_power_rule(
        self,
        server_runtime: Dict[str, Any],
        skill_meta: Dict[str, Any],
        base_power: int,
    ) -> None:
        """按技能白名单把服务器同步威力转换为额外倍率。"""
        damage_server_runtime.apply_server_power_rule(
            server_runtime,
            skill_meta,
            base_power,
            self._server_power_rules,
        )

    def _resolve_power(
        self,
        power: int,
        skill_meta: Dict[str, Any],
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
    ) -> Tuple[int, Dict[str, Any]]:
        """阶段 1: pre_power hook — 可修正威力。"""
        ctx = self._run_hooks("pre_power", {
            "power": power,
            "skill_meta": skill_meta,
            "attacker": attacker,
            "defender": defender,
        })
        return ctx["power"], ctx

    def _resolve_combat_stats(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        damage_type: int,
        power: int,
    ) -> Optional[Tuple[float, float, float, str, List[str], Dict[str, str]]]:
        """获取有效攻防属性、能力等级和置信度。返回 None 如果无法获取属性。"""
        del power
        return combat_stats.resolve_combat_stats(attacker, defender, damage_type)

    def _compute_base_damage(
        self,
        power: int,
        eff_atk: float,
        eff_def: float,
        skill_meta: Dict[str, Any],
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
    ) -> float:
        """阶段 2: 基础伤害公式 + post_base hook。"""
        base = damage_formula.base_damage(eff_atk, eff_def, power)
        ctx = self._run_hooks("post_base", {
            "base_damage": base,
            "power": power,
            "atk_val": eff_atk,
            "def_val": eff_def,
            "skill_meta": skill_meta,
            "attacker": attacker,
            "defender": defender,
        })
        return ctx["base_damage"]

    def _apply_multipliers(
        self,
        base: float,
        skill_element: int,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        skill_meta: Dict[str, Any],
        weather: Optional[Dict[str, Any]],
        server_runtime: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, float, float, float, float, str, bool]:
        """阶段 3: 属性克制、STAB、天气、pre_final hook。"""
        return damage_multipliers.apply_damage_multipliers(
            damage_multipliers.DamageMultiplierInput(
                base_damage=base,
                skill_element=skill_element,
                attacker=attacker,
                defender=defender,
                skill_meta=skill_meta,
                weather=weather,
                server_runtime=server_runtime,
            ),
            get_multiplier=self.chart.get_multiplier,
            get_effectiveness_label=self.chart.get_effectiveness_label,
            run_hooks=self._run_hooks,
        ).as_legacy_tuple()

    def _finalize_damage(
        self,
        dmg: int,
        power: int,
        ability_level: float,
        effective_atk: float,
        effective_def: float,
        effectiveness: float,
        stab_mult: float,
        weather_mult: float,
        power_mult: float,
        skill_meta: Dict[str, Any],
        skill_element: int,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        damage_type: int,
        eff_label: str,
        is_stab: bool,
        confidence: str,
        warnings: List[str],
        stat_sources: Dict[str, str],
        runtime_skill: Optional[Dict[str, Any]] = None,
        server_runtime: Optional[Dict[str, Any]] = None,
        final_power: Optional[int] = None,
    ) -> DamageResult:
        """阶段 4: post_calc hook、连击、HP%、能耗、构造结果。"""
        return finalize_damage_result(
            DamageFinalizeInput(
                dmg=dmg,
                power=power,
                ability_level=ability_level,
                effective_atk=effective_atk,
                effective_def=effective_def,
                effectiveness=effectiveness,
                stab_mult=stab_mult,
                weather_mult=weather_mult,
                power_mult=power_mult,
                skill_meta=skill_meta,
                skill_element=skill_element,
                attacker=attacker,
                defender=defender,
                damage_type=damage_type,
                eff_label=eff_label,
                is_stab=is_stab,
                confidence=confidence,
                warnings=warnings,
                stat_sources=stat_sources,
                runtime_skill=runtime_skill,
                server_runtime=server_runtime,
                final_power=final_power,
                special_fixed_light_skills=SPECIAL_FIXED_LIGHT_SKILLS,
            ),
            run_hooks=self._run_hooks,
            type_name=self.chart.type_name,
        )
