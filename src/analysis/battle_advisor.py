"""战斗分析协调器 — 汇总各分析模块生成结构化建议。

BattleAdvisor 是伤害分析的入口点，它:
1. 创建 DamageCalculator 并注册先天技能 hook
2. 接收战斗状态，为每个装备技能计算伤害预测
3. 生成建议（击杀提示、效果拔群、抵抗警告、能量不足）

输出为 BattleAdvice 数据结构:
  - skill_analysis: 所有装备技能的详细分析（含伤害预测）
  - suggestions: 基于分析的建议列表
  - traits: 检测到的我方先天技能特征
  - opp_traits: 检测到的对方先天技能特征
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.advisor.skill_analysis import build_skill_analysis, eval_skill_dict, skill_from_equipped
from src.analysis.advisor.suggestions import build_advisor_suggestions
from src.analysis.advisor.traits import extract_traits
from src.analysis.damage_prediction import DamagePredictionService
from src.analysis.models import BattleAdvice, SkillAnalysis
from src.analysis.skill_resolver import resolve_equipped_or_pool, resolve_opponent_skills, skills_from_pool
from src.game.type_chart import TypeChart


class BattleAdvisor:
    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self.chart = type_chart or TypeChart()
        self._prediction_service = DamagePredictionService(self.chart)
        self._damage_calc = self._prediction_service._damage_calc

    def analyze(self, state: Dict[str, Any]) -> BattleAdvice:
        my_active = state.get("my_active")
        opp_active = state.get("opp_active")
        if not my_active or not opp_active:
            return BattleAdvice()

        equipped = resolve_equipped_or_pool(my_active)

        weather = state.get("weather")
        skill_analysis = self._build_skill_analysis(my_active, opp_active, equipped, weather)
        my_pets = state.get("my_pets", [])
        suggestions = self._build_suggestions(my_active, opp_active, skill_analysis, my_pets)
        traits = self._extract_traits(my_active)
        opp_traits = self._extract_traits(opp_active)

        # 对手技能分析：优先协议数据，回退到热门预设
        opp_equipped, opp_source = resolve_opponent_skills(opp_active)
        opp_skill_analysis: List[SkillAnalysis] = []
        if opp_equipped:
            raw = self._build_skill_analysis(
                opp_active, my_active, opp_equipped, weather,
            )
            # 过滤无名技能并限制数量（PvP 常规 4 个，首领化 7 个）
            opp_skill_analysis = [
                sa for sa in raw
                if sa.skill_name and sa.skill_name != "?"
            ][:4]

        return BattleAdvice(
            skill_analysis=skill_analysis,
            suggestions=suggestions,
            traits=traits,
            opp_traits=opp_traits,
            opp_skill_analysis=opp_skill_analysis,
            opp_skill_source=opp_source,
        )

    def _build_skill_analysis(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        equipped: List[Dict[str, Any]],
        weather: Optional[Dict[str, Any]] = None,
    ) -> List[SkillAnalysis]:
        return build_skill_analysis(
            prediction_service=self._prediction_service,
            chart=self.chart,
            attacker=attacker,
            defender=defender,
            equipped=equipped,
            weather=weather,
        )

    @staticmethod
    def _skill_from_equipped(
        eq: Dict[str, Any], meta: Optional[Dict[str, Any]],
    ) -> SkillAnalysis:
        return skill_from_equipped(eq, meta)

    @staticmethod
    def _eval_skill_dict(eq: Dict[str, Any], meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return eval_skill_dict(eq, meta)

    def _build_suggestions(
        self,
        my_active: Dict[str, Any],
        opp_active: Dict[str, Any],
        skill_analysis: List[SkillAnalysis],
        my_pets: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, str]]:
        return build_advisor_suggestions(
            chart=self.chart,
            my_active=my_active,
            opp_active=opp_active,
            skill_analysis=skill_analysis,
            my_pets=my_pets,
        )

    @staticmethod
    def _skills_from_pool(pet: Dict[str, Any]) -> List[Dict[str, Any]]:
        return skills_from_pool(pet)

    @staticmethod
    def _resolve_opp_skills(opp_active: Dict[str, Any]) -> tuple:
        return resolve_opponent_skills(opp_active)

    @staticmethod
    def _extract_traits(pet: Dict[str, Any]) -> List[Dict[str, str]]:
        return extract_traits(pet)
