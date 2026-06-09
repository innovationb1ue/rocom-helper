"""非伤害技能的战术评分规则。"""
from __future__ import annotations

from typing import Any, Callable, Dict, Tuple

from src.analysis.skill_classifier import classify_skill_effect
from src.analysis.tactical import presentation

AssessConfidenceFn = Callable[[Dict[str, Any]], str]


def score_non_damage_skill(
    our_action: Dict[str, Any],
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    *,
    assess_confidence: AssessConfidenceFn,
) -> Tuple[float, str, Dict[str, Any]]:
    """非伤害技能的结构化评分。"""
    base = 0.15
    meta = our_action.get("meta", {})
    tags = classify_skill_effect(meta)

    hp_pct = my_active.get("hp_pct", 1.0)
    our_speed = my_active.get("effective_speed") or my_active.get("base_speed", 0)
    opp_speed = opp_active.get("effective_speed") or opp_active.get("base_speed", 0)
    we_outspeed = our_speed >= opp_speed

    if "stat_up" in tags:
        if "spd_up" in tags or "speed" in tags:
            base += 0.08
        elif we_outspeed:
            base += 0.06
        else:
            base += 0.04

    if "stat_down" in tags:
        base += 0.05

    if "heal" in tags:
        if hp_pct < 0.3:
            base += 0.12
        elif hp_pct < 0.5:
            base += 0.08
        else:
            base += 0.03

    if "shield" in tags:
        if hp_pct < 0.5:
            base += 0.07
        else:
            base += 0.04

    if "damage_reduce" in tags:
        base += 0.05

    if "cleanse" in tags:
        buffs = my_active.get("buffs", [])
        negative_buffs = [buff for buff in buffs if buff.get("stage", 0) < 0]
        if negative_buffs:
            base += 0.06

    if "hazard" in tags:
        base += 0.04

    energy_cost = our_action.get("energy_cost", 0)
    base -= 0.015 * energy_cost
    base = max(0.05, base)

    reason = our_action.get("skill_name", "辅助技能")
    if tags:
        reason += f" ({','.join(tags[:3])})"
    unknowns = presentation.action_unknowns(our_action, opp_active, {})
    detail = {
        "damage_dealt": None,
        "damage_taken": None,
        "can_ko": False,
        "category": "conservative" if "heal" in tags or "shield" in tags else "setup",
        "expected_gain": "强化/回复类收益，适合拉长回合",
        "risk": "直接输出较低，若对手爆发可能亏节奏",
        "confidence": presentation.action_confidence(unknowns, opp_active, assess_confidence),
        "metrics": {
            "energy_after": max(0, my_active.get("energy", 10) - energy_cost),
            "effect_tags": tags,
        },
        "unknowns": unknowns,
    }
    return base, reason, detail
