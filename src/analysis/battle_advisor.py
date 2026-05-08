"""战斗分析协调器 — 汇总各分析模块生成结构化建议。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.analysis.damage_calc import DamageCalculator, DamageResult
from src.game.type_chart import TypeChart


@dataclass
class BattleAdvice:
    damage_predictions: List[DamageResult] = field(default_factory=list)
    best_damage_skill: Optional[DamageResult] = None
    suggestions: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "damage_predictions": [p.to_dict() for p in self.damage_predictions],
            "suggestions": self.suggestions,
        }
        if self.best_damage_skill is not None:
            d["best_damage_skill"] = self.best_damage_skill.to_dict()
        return d


class BattleAdvisor:
    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self.chart = type_chart or TypeChart()
        self._damage_calc = DamageCalculator(self.chart)

    def analyze(self, state: Dict[str, Any]) -> BattleAdvice:
        """对当前战斗状态进行分析，返回建议。"""
        my_active = state.get("my_active")
        opp_active = state.get("opp_active")
        if not my_active or not opp_active:
            return BattleAdvice()

        # 收集技能列表：优先 used_skills > equipped_skills > skills > base_skill_pool
        skills = my_active.get("used_skills") or []
        if not skills:
            skills = my_active.get("equipped_skills") or my_active.get("skills") or []
        if not skills:
            skills = self._skills_from_pool(my_active)
        predictions = self._damage_calc.calculate_all(my_active, opp_active, skills)

        # 最佳伤害技能
        best = predictions[0] if predictions else None

        # 生成文本建议
        suggestions = self._build_suggestions(my_active, opp_active, predictions)

        return BattleAdvice(
            damage_predictions=predictions,
            best_damage_skill=best,
            suggestions=suggestions,
        )

    def _build_suggestions(
        self,
        my_active: Dict[str, Any],
        opp_active: Dict[str, Any],
        predictions: List[DamageResult],
    ) -> List[Dict[str, str]]:
        """从伤害预测中提取文本建议。"""
        suggestions: List[Dict[str, str]] = []

        if not predictions:
            return suggestions

        best = predictions[0]
        if best.can_ko:
            suggestions.append({
                "type": "ko_skill",
                "message": f"{best.skill_name} 可以击杀 {opp_active.get('name', '对方精灵')}！",
            })
        elif best.effectiveness >= 2.0:
            suggestions.append({
                "type": "super_effective",
                "message": f"{best.skill_name} 效果拔群，预计造成 {best.min_damage}~{best.max_damage} 伤害",
            })
        elif best.effectiveness < 1.0 and best.effectiveness > 0:
            suggestions.append({
                "type": "resisted",
                "message": f"所有攻击技能均被抵抗，考虑换宠",
            })

        # 能量不足警告
        low_energy_skills = [p for p in predictions if "能量不足" in "".join(p.warnings)]
        if len(low_energy_skills) == len(predictions) and predictions:
            suggestions.append({
                "type": "no_energy",
                "message": "能量不足以使用任何攻击技能",
            })

        return suggestions

    @staticmethod
    def _skills_from_pool(pet: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从 base_skill_pool 中构建技能列表（回退方案）。"""
        pool = pet.get("base_skill_pool")
        if not pool:
            return []
        skills = []
        for entry in pool:
            skill_id = entry.get("skill_id")
            if skill_id is None:
                continue
            skills.append({"skill_id": skill_id})
        return skills
