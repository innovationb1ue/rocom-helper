"""技能伤害分析构建。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.constants import SDT_TO_TYPE
from src.analysis.damage_prediction import DamagePredictionService
from src.analysis.models import SkillAnalysis
from src.data.loader import get_skill_meta, get_skill_name
from src.game.skill_eval import score_skill
from src.game.type_chart import TypeChart


def build_skill_analysis(
    *,
    prediction_service: DamagePredictionService,
    chart: TypeChart,
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
        sa = skill_from_equipped(eq, meta)
        damage_type = sa.skill_damage_type
        if meta and damage_type in (2, 3):
            pred = prediction_service.predict(attacker, defender, meta, weather=weather)
            if pred is not None:
                dr = pred["result"]
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
                sa.prediction = pred["prediction"]
                sa.explain = pred["explain"]
                sa.validation_hint = pred["validation_hint"]
        eval_dict = eval_skill_dict(eq, meta)
        sa._quality_score = round(score_skill(eval_dict, chart), 1)
        results.append(sa)
    results.sort(key=lambda s: s.equipped_slot)
    return results


def skill_from_equipped(
    eq: Dict[str, Any], meta: Optional[Dict[str, Any]],
) -> SkillAnalysis:
    skill_id = eq.get("skill_id", 0)
    slot = eq.get("equipped_slot", 0)
    name = eq.get("skill_name") or get_skill_name(skill_id) or "?"
    element = eq.get("skill_element") or 0
    damage_type = eq.get("skill_damage_type") or (meta.get("damage_type", 0) if meta else 0)
    energy_cost = eq.get("runtime_cost_energy")
    if energy_cost is None:
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


def eval_skill_dict(eq: Dict[str, Any], meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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

