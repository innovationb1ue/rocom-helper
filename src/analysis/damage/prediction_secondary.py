"""伤害预测的附带二段效果规则。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.analysis.damage.result import DamageResult

POISON_CAPSULE_SKILL_ID = 7120090
POISON_ELEMENT_ID = 7
POISON_TICK_RATIO = 0.03


def secondary_effects(dr: DamageResult, defender: Dict[str, Any]) -> List[Dict[str, Any]]:
    """构造直接伤害之后的战术附带效果。"""
    if dr.skill_id != POISON_CAPSULE_SKILL_ID:
        return []
    defender_types = set(defender.get("types") or [])
    if POISON_ELEMENT_ID in defender_types:
        return []
    max_hp = int(dr.damage_breakdown.get("defender_max_hp") or defender.get("max_hp") or 0)
    current_hp = int(dr.damage_breakdown.get("defender_current_hp") or defender.get("current_hp") or 0)
    if max_hp <= 0 or current_hp <= 0:
        return []
    hp_after_direct = max(0, current_hp - dr.total_damage)
    if hp_after_direct <= 0:
        return []
    tick = max(1, int(max_hp * POISON_TICK_RATIO))
    tick = min(tick, hp_after_direct)
    return [{
        "kind": "poison_tick",
        "name": "中毒当回合结算",
        "damage": tick,
        "ratio": POISON_TICK_RATIO,
        "timing": "after_skill_damage",
        "audit_policy": "excluded_from_direct_damage",
        "notes": "毒囊先造成本体伤害，再施加中毒；中毒在当前回合额外结算一次。",
    }]
