"""战斗分析协调器 — 汇总各分析模块生成结构化建议。

BattleAdvisor 是伤害分析的入口点，它:
1. 创建 DamageCalculator 并注册先天技能 hook
2. 接收战斗状态，为每个装备技能计算伤害预测
3. 生成建议（击杀提示、效果拔群、抵抗警告、能量不足）

输出为 BattleAdvice 数据结构:
  - skill_analysis: 所有装备技能的详细分析（含伤害预测）
  - suggestions: 基于分析的建议列表
  - traits: 检测到的先天技能特征
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.analysis.damage_calc import DamageCalculator, DamageResult
from src.analysis.innate_hooks import register_innate_hooks
from src.data.loader import get_skill_meta, get_skill_name
from src.game.type_chart import TypeChart


@dataclass
class SkillAnalysis:
    """单个技能的完整分析（基础信息 + 伤害预测）。"""
    skill_id: int
    skill_name: str
    equipped_slot: int
    skill_element: int
    skill_damage_type: int
    energy_cost: int
    skill_desc: Optional[str] = None
    power: Optional[int] = None
    min_damage: Optional[int] = None
    max_damage: Optional[int] = None
    total_min_damage: Optional[int] = None
    total_max_damage: Optional[int] = None
    effectiveness: Optional[float] = None
    effectiveness_label: Optional[str] = None
    is_stab: Optional[bool] = None
    can_ko: Optional[bool] = None
    hit_count: int = 1
    confidence: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BattleAdvice:
    skill_analysis: List[SkillAnalysis] = field(default_factory=list)
    suggestions: List[Dict[str, str]] = field(default_factory=list)
    traits: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_analysis": [s.to_dict() for s in self.skill_analysis],
            "suggestions": self.suggestions,
            "traits": self.traits,
        }


class BattleAdvisor:
    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self.chart = type_chart or TypeChart()
        self._damage_calc = DamageCalculator(self.chart)
        register_innate_hooks(self._damage_calc)

    def analyze(self, state: Dict[str, Any]) -> BattleAdvice:
        my_active = state.get("my_active")
        opp_active = state.get("opp_active")
        if not my_active or not opp_active:
            return BattleAdvice()

        equipped = my_active.get("equipped_skills") or my_active.get("skills") or my_active.get("used_skills") or []
        if not equipped:
            equipped = self._skills_from_pool(my_active)

        skill_analysis = self._build_skill_analysis(my_active, opp_active, equipped)
        suggestions = self._build_suggestions(my_active, opp_active, skill_analysis)
        traits = self._extract_traits(my_active)

        return BattleAdvice(
            skill_analysis=skill_analysis,
            suggestions=suggestions,
            traits=traits,
        )

    # 技能分析管线:
    # 1. 从装备技能列表获取 skill_id
    # 2. 查询技能 meta 数据
    # 3. 如果是攻击技能 (damage_type=2/3)，调用 DamageCalculator.calculate()
    # 4. 合并基础信息和伤害预测结果
    def _build_skill_analysis(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        equipped: List[Dict[str, Any]],
    ) -> List[SkillAnalysis]:
        results: List[SkillAnalysis] = []
        for eq in equipped:
            skill_id = eq.get("skill_id")
            if skill_id is None:
                continue
            meta = get_skill_meta(skill_id)
            sa = self._skill_from_equipped(eq, meta)
            damage_type = sa.skill_damage_type
            if meta and damage_type in (2, 3):
                dr = self._damage_calc.calculate(attacker, defender, meta)
                if dr is not None:
                    sa.power = dr.power
                    sa.min_damage = dr.min_damage
                    sa.max_damage = dr.max_damage
                    sa.total_min_damage = dr.total_min_damage
                    sa.total_max_damage = dr.total_max_damage
                    sa.effectiveness = dr.effectiveness
                    sa.effectiveness_label = dr.effectiveness_label
                    sa.is_stab = dr.is_stab
                    sa.can_ko = dr.can_ko
                    sa.hit_count = dr.hit_count
                    sa.confidence = dr.confidence
                    sa.warnings = dr.warnings
            results.append(sa)
        results.sort(key=lambda s: s.equipped_slot)
        return results

    @staticmethod
    def _skill_from_equipped(
        eq: Dict[str, Any], meta: Optional[Dict[str, Any]],
    ) -> SkillAnalysis:
        skill_id = eq.get("skill_id", 0)
        slot = eq.get("equipped_slot", 0)
        name = eq.get("skill_name") or get_skill_name(skill_id) or "?"
        element = eq.get("skill_element") or 0
        damage_type = eq.get("skill_damage_type") or (meta.get("damage_type", 0) if meta else 0)
        energy_cost = eq.get("cost_energy")
        if energy_cost is None and meta:
            ec = meta.get("energy_cost", [0])
            energy_cost = ec[0] if ec else 0
        if energy_cost is None:
            energy_cost = 0
        desc = eq.get("skill_desc")
        if desc is None and meta:
            desc = meta.get("desc")
        if element == 0 and meta:
            from src.protocol.proto_core import SDT_TO_TYPE
            dt = meta.get("skill_dam_type")
            if dt is not None:
                element = SDT_TO_TYPE.get(dt, 0)
        return SkillAnalysis(
            skill_id=skill_id,
            skill_name=name,
            equipped_slot=slot,
            skill_element=element,
            skill_damage_type=damage_type,
            energy_cost=energy_cost,
            skill_desc=desc,
        )

    def _build_suggestions(
        self,
        my_active: Dict[str, Any],
        opp_active: Dict[str, Any],
        skill_analysis: List[SkillAnalysis],
    ) -> List[Dict[str, str]]:
        suggestions: List[Dict[str, str]] = []
        attack_skills = [s for s in skill_analysis if s.min_damage is not None]
        if not attack_skills:
            return suggestions

        best = max(attack_skills, key=lambda s: s.max_damage or 0)
        if best.can_ko:
            suggestions.append({
                "type": "ko_skill",
                "message": f"{best.skill_name} 可以击杀 {opp_active.get('name', '对方精灵')}！",
            })
        elif best.effectiveness is not None and best.effectiveness >= 2.0:
            suggestions.append({
                "type": "super_effective",
                "message": f"{best.skill_name} 效果拔群，预计造成 {best.min_damage}~{best.max_damage} 伤害",
            })
        elif best.effectiveness is not None and 0 < best.effectiveness < 1.0:
            suggestions.append({
                "type": "resisted",
                "message": "所有攻击技能均被抵抗，考虑换宠",
            })

        low_energy = [s for s in attack_skills if "能量不足" in "".join(s.warnings)]
        if len(low_energy) == len(attack_skills) and attack_skills:
            suggestions.append({
                "type": "no_energy",
                "message": "能量不足以使用任何攻击技能",
            })

        return suggestions

    @staticmethod
    def _skills_from_pool(pet: Dict[str, Any]) -> List[Dict[str, Any]]:
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

    @staticmethod
    def _extract_traits(pet: Dict[str, Any]) -> List[Dict[str, str]]:
        from src.data.loader import get_innate_skill, get_pet_innate_trait
        traits: List[Dict[str, str]] = []
        seen_names: set = set()

        def _add(name: str, description: str) -> None:
            if name and name not in seen_names:
                seen_names.add(name)
                traits.append({"name": name, "description": description})

        # Source 1: wiki_pets.json — authoritative pet → trait mapping
        wiki_trait = get_pet_innate_trait(pet.get("name", ""))
        if wiki_trait:
            _add(wiki_trait["name"], wiki_trait.get("description", ""))

        # Source 2: innate_skill_id from protocol (cur_passive_skill)
        innate_id = pet.get("innate_skill_id")
        if innate_id:
            innate = get_innate_skill(innate_id)
            if innate is not None:
                _add(innate.get("name", "?"), innate.get("description", ""))

        # Source 3: buff list — only known innate skills from innate_skills.json
        for buff in pet.get("buffs", []):
            buff_id = buff.get("id")
            if buff_id is None:
                continue
            innate = get_innate_skill(buff_id)
            if innate is not None:
                _add(innate.get("name", "?"), innate.get("description", ""))

        return traits
