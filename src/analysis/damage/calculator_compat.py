"""Legacy private helper methods for DamageCalculator compatibility."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.analysis.damage import combat_stats
from src.analysis.damage import formula as damage_formula
from src.analysis.damage import result as damage_result
from src.analysis.damage import runtime as damage_runtime
from src.analysis.damage import server_runtime as damage_server_runtime


class DamageCalculatorCompatMixin:
    """Keep historical `DamageCalculator._*` helper imports working."""

    @staticmethod
    def _collect_derived_buffs(buff_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return damage_result.collect_derived_buffs(buff_list)

    @staticmethod
    def _runtime_sources(runtime_skill: Dict[str, Any], server_runtime: Dict[str, Any]) -> Dict[str, Any]:
        """汇总服务端同步运行时字段，供预测解释和审计使用。"""
        return damage_runtime.runtime_sources(runtime_skill, server_runtime)

    @staticmethod
    def _base_damage(atk: float, def_: float, power: int) -> float:
        """NRC_AI 基础伤害公式: (ATK/DEF) * power * 0.9"""
        return damage_formula.base_damage(atk, def_, power)

    @staticmethod
    def _get_power(skill_meta: Dict[str, Any]) -> int:
        return damage_result.skill_power(skill_meta)

    @staticmethod
    def _get_runtime_skill(attacker: Dict[str, Any], skill_id: Any) -> Dict[str, Any]:
        """从状态机的 skill_runtime 中读取当前战斗里的技能同步参数。"""
        return damage_runtime.get_runtime_skill(attacker, skill_id)

    @staticmethod
    def _target_keys(pet: Dict[str, Any]) -> List[str]:
        return damage_runtime.target_keys(pet)

    @staticmethod
    def _restraint_to_multiplier(value: Any) -> Optional[float]:
        return damage_runtime.restraint_to_multiplier(value)

    def _resolve_server_runtime(self, runtime_skill: Dict[str, Any], defender: Dict[str, Any]) -> Dict[str, Any]:
        """按目标读取服务器同步的技能威力参数和克制结果。"""
        return damage_server_runtime.resolve_server_runtime(runtime_skill, defender)

    @staticmethod
    def _resolve_energy_cost(runtime_skill: Dict[str, Any], skill_meta: Dict[str, Any]) -> Tuple[int, str]:
        return damage_runtime.resolve_energy_cost(runtime_skill, skill_meta)

    @staticmethod
    def _get_stat_with_source(pet: Dict[str, Any], stat_name: str) -> Tuple[Optional[int], str]:
        """从抓包数据中提取属性值和来源。来源: 'total', 'calc_bonus', ''。"""
        return combat_stats.get_stat_with_source(pet, stat_name)

    @staticmethod
    def _get_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
        """从抓包数据中提取属性值。"""
        return combat_stats.get_stat(pet, stat_name)

    @staticmethod
    def _calc_arena_stat(race_value: int, stat_name: str) -> int:
        """用 NRC_AI 竞技场公式估算平衡后属性值 (IV=0, 性格=坦率)."""
        return combat_stats.calc_arena_stat(race_value, stat_name)

    @staticmethod
    def _nature_modifiers(pet: Dict[str, Any]) -> Dict[str, float]:
        return combat_stats.nature_modifiers(pet)

    @staticmethod
    def _get_pvp_template_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
        """从 pet_species 种族值按 PvP 通用模板估算平衡后属性值。"""
        return combat_stats.get_pvp_template_stat(pet, stat_name)

    @staticmethod
    def _get_wiki_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
        """旧兜底接口。当前没有独立 wiki 属性源，保留为兼容入口。"""
        return combat_stats.get_wiki_stat(pet, stat_name)

    @staticmethod
    def _get_base_hit_count(skill_meta: Dict[str, Any]) -> int:
        return damage_result.base_hit_count(skill_meta)
