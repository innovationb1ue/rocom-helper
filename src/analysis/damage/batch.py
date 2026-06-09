"""批量伤害预测编排。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from src.analysis.damage.result import DamageResult
from src.data.loader import get_skill_meta


class SkillDamageCalculator(Protocol):
    def calculate(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        skill_meta: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
    ) -> Optional[DamageResult]:
        ...


def calculate_all_skills(
    calculator: SkillDamageCalculator,
    attacker: Dict[str, Any],
    defender: Dict[str, Any],
    skills: List[Dict[str, Any]],
    weather: Optional[Dict[str, Any]] = None,
) -> List[DamageResult]:
    """计算所有可解析攻击技能，并按最大总伤害降序排列。"""
    results: List[DamageResult] = []
    for skill in skills:
        skill_id = skill.get("skill_id")
        if skill_id is None:
            continue
        meta = get_skill_meta(skill_id)
        if meta is None:
            continue
        result = calculator.calculate(attacker, defender, meta, weather=weather)
        if result is not None:
            results.append(result)
    results.sort(key=lambda r: r.total_max_damage, reverse=True)
    return results
