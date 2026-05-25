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

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.analysis.damage_calc import DamageCalculator, DamageResult
from src.analysis.innate_hooks import register_innate_hooks
from src.analysis.constants import SDT_TO_TYPE
from src.analysis.pet_identity import same_battle_pet
from src.data.loader import get_skill_meta, get_skill_name, get_popular_skills
from src.game.type_chart import TypeChart
from src.game.skill_eval import score_skill
from src.analysis.counter import CounterPicker


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
    effective_power: Optional[int] = None
    expected_damage: Optional[int] = None
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
    power_mult: Optional[float] = None
    weather_mult: Optional[float] = None
    damage_breakdown: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)
    _quality_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BattleAdvice:
    skill_analysis: List[SkillAnalysis] = field(default_factory=list)
    suggestions: List[Dict[str, str]] = field(default_factory=list)
    traits: List[Dict[str, str]] = field(default_factory=list)
    opp_traits: List[Dict[str, str]] = field(default_factory=list)
    opp_skill_analysis: List[SkillAnalysis] = field(default_factory=list)
    opp_skill_source: str = ""  # "protocol" | "preset" | ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_analysis": [s.to_dict() for s in self.skill_analysis],
            "suggestions": self.suggestions,
            "traits": self.traits,
            "opp_traits": self.opp_traits,
            "opp_skill_analysis": [s.to_dict() for s in self.opp_skill_analysis],
            "opp_skill_source": self.opp_skill_source,
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

        weather = state.get("weather")
        skill_analysis = self._build_skill_analysis(my_active, opp_active, equipped, weather)
        my_pets = state.get("my_pets", [])
        suggestions = self._build_suggestions(my_active, opp_active, skill_analysis, my_pets)
        traits = self._extract_traits(my_active)
        opp_traits = self._extract_traits(opp_active)

        # 对手技能分析：优先协议数据，回退到热门预设
        opp_equipped, opp_source = self._resolve_opp_skills(opp_active)
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
        results: List[SkillAnalysis] = []
        for eq in equipped:
            skill_id = eq.get("skill_id")
            if skill_id is None:
                continue
            meta = get_skill_meta(skill_id)
            sa = self._skill_from_equipped(eq, meta)
            damage_type = sa.skill_damage_type
            if meta and damage_type in (2, 3):
                dr = self._damage_calc.calculate(attacker, defender, meta, weather=weather)
                if dr is not None:
                    sa.power = dr.power
                    sa.effective_power = dr.effective_power
                    sa.expected_damage = dr.expected_damage
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
                    sa.power_mult = dr.power_mult
                    sa.weather_mult = dr.weather_mult
                    sa.damage_breakdown = dr.damage_breakdown
                    sa.warnings = dr.warnings
            # 技能综合质量评分
            eval_dict = self._eval_skill_dict(eq, meta)
            sa._quality_score = round(score_skill(eval_dict, self.chart), 1)
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

    @staticmethod
    def _eval_skill_dict(eq: Dict[str, Any], meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """构造适合 skill_eval.score_skill 的技能字典。"""
        power = 0
        energy_cost = eq.get("cost_energy") or 0
        accuracy = 100
        pp = 20
        type_id = eq.get("skill_element") or 0
        effect_desc = eq.get("skill_desc")

        if meta:
            dam_para = meta.get("dam_para", [])
            power = dam_para[0] if dam_para else 0
            ec = meta.get("energy_cost", [0])
            energy_cost = energy_cost or (ec[0] if ec else 0)
            hit_para = meta.get("hit_para")
            if hit_para is not None:
                accuracy = hit_para / 100
            pp = meta.get("max_pp", 20)
            effect_desc = effect_desc or meta.get("desc")
            dt = meta.get("skill_dam_type")
            if dt is not None:
                type_id = SDT_TO_TYPE.get(dt, type_id)

        return {
            "power": power,
            "energy_cost": energy_cost,
            "accuracy": accuracy,
            "pp": pp,
            "type_id": type_id,
            "effect_desc": effect_desc,
        }

    def _build_suggestions(
        self,
        my_active: Dict[str, Any],
        opp_active: Dict[str, Any],
        skill_analysis: List[SkillAnalysis],
        my_pets: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, str]]:
        suggestions: List[Dict[str, str]] = []
        attack_skills = [s for s in skill_analysis if s.expected_damage is not None]
        if not attack_skills:
            return suggestions

        best = max(attack_skills, key=lambda s: s.total_max_damage or 0)
        if best.can_ko:
            suggestions.append({
                "type": "ko_skill",
                "message": f"{best.skill_name} 可以击杀 {opp_active.get('name', '对方精灵')}！",
            })
        elif best.effectiveness is not None and best.effectiveness >= 2.0:
            suggestions.append({
                "type": "super_effective",
                "message": f"{best.skill_name} 效果拔群，预计造成 {best.expected_damage} 伤害",
            })
        elif best.effectiveness is not None and 0 < best.effectiveness < 1.0:
            suggestions.append({
                "type": "resisted",
                "message": "所有攻击技能均被抵抗，考虑换宠",
            })
            # team-level 反制建议
            if my_pets:
                living = [
                    p for p in my_pets
                    if p.get("current_hp", 1) > 0 and not same_battle_pet(p, my_active)
                ]
                if living:
                    picker = CounterPicker(self.chart)
                    norm_opp = {"types": opp_active.get("types", [])}
                    norm_living = [
                        {
                            "types": p.get("types", []),
                            "pet_id": p.get("pet_id"),
                            "name": p.get("name"),
                            "slot": p.get("slot"),
                            "side": p.get("side"),
                            "base_conf_id": p.get("base_conf_id"),
                            "battle_uid": p.get("battle_uid"),
                        }
                        for p in living
                    ]
                    counters = picker.find_counters([norm_opp], norm_living, top_n=1)
                    if counters:
                        name = counters[0].get("name", "未知")
                        suggestions.append({
                            "type": "counter_switch",
                            "message": f"当前对位被全面克制，建议换上 {name} 进行反制",
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
    def _resolve_opp_skills(opp_active: Dict[str, Any]) -> tuple:
        """解析对手技能：优先协议装备技能 → 已使用技能 → 热门预设。

        Returns:
            (skill_list, source) — source 为 "protocol" | "used" | "preset" | ""
        """
        # 1. 优先使用协议中的装备技能
        equipped = (
            opp_active.get("equipped_skills")
            or opp_active.get("skills")
            or []
        )
        if equipped:
            return equipped, "protocol"

        # 2. 回退到对手已使用过的技能（从战斗事件中追踪）
        used = opp_active.get("used_skills") or []
        if used:
            return used, "used"

        # 3. 回退到热门技能预设
        base_id = opp_active.get("base_id") or opp_active.get("base_conf_id")
        if base_id:
            preset = get_popular_skills(base_id)
            if preset and preset.get("skills"):
                return [
                    {"skill_id": sid} for sid in preset["skills"]
                ], "preset"

        return [], ""

    @staticmethod
    def _extract_traits(pet: Dict[str, Any]) -> List[Dict[str, str]]:
        from src.data.loader import get_innate_skill, get_pet_innate_trait
        traits: List[Dict[str, str]] = []
        seen_names: set = set()

        def _add(name: str, description: str) -> None:
            if name and name not in seen_names:
                seen_names.add(name)
                traits.append({"name": name, "description": description})

        # Source 1: pet_species.pet_feature → skill_map.name (authoritative trait mapping)
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


def build_state_suggestions(state: Dict[str, Any]) -> List[Dict[str, str]]:
    """基于当前战斗状态的实时建议（低血量、击杀机会、能量不足、负面状态）。"""
    suggestions: List[Dict[str, str]] = []
    seen: set = set()
    my_active = state.get("my_active")
    opp_active = state.get("opp_active")

    if my_active is None or opp_active is None:
        return suggestions

    my_hp_pct = my_active.get("hp_pct", 1.0)
    if my_hp_pct < 0.25:
        suggestions.append({"type": "low_hp", "message": "我方精灵HP过低，考虑换宠"})

    opp_hp_pct = opp_active.get("hp_pct", 1.0)
    if opp_hp_pct < 0.25:
        suggestions.append({"type": "finish_off", "message": "对手精灵HP极低，可尝试击杀"})

    if my_active.get("energy", 0) < 2:
        suggestions.append({"type": "low_energy", "message": "能量不足，考虑使用低能耗技能或能量瓶"})

    my_buffs = my_active.get("buffs", [])
    negative_buffs = [b for b in my_buffs if b.get("stacks", 0) < 0]
    if len(negative_buffs) >= 2:
        suggestions.append({"type": "debuffed", "message": "我方精灵有多个负面状态"})

    unique: List[Dict[str, str]] = []
    for s in suggestions:
        key = (s["type"], s["message"])
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique
