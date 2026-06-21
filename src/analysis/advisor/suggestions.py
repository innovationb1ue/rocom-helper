"""BattleAdvisor 的技能建议构建。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.counter import CounterPicker
from src.analysis.models import SkillAnalysis
from src.analysis.pet_identity import same_battle_pet
from src.game.type_chart import TypeChart


def build_advisor_suggestions(
    *,
    chart: TypeChart,
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
        if my_pets:
            _append_counter_switch_suggestion(
                suggestions=suggestions,
                chart=chart,
                my_active=my_active,
                opp_active=opp_active,
                my_pets=my_pets,
            )

    low_energy = [s for s in attack_skills if "能量不足" in "".join(s.warnings)]
    if len(low_energy) == len(attack_skills) and attack_skills:
        suggestions.append({
            "type": "no_energy",
            "message": "能量不足以使用任何攻击技能",
        })

    return suggestions


def _append_counter_switch_suggestion(
    *,
    suggestions: List[Dict[str, str]],
    chart: TypeChart,
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    my_pets: List[Dict[str, Any]],
) -> None:
    living = [
        p for p in my_pets
        if p.get("current_hp", 1) > 0 and not same_battle_pet(p, my_active)
    ]
    if not living:
        return

    picker = CounterPicker(chart)
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

