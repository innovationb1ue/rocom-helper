"""能量监控纯规则 — 供 EnergyMonitorHook 和单元测试复用。"""
from __future__ import annotations

from typing import Any, Dict, List


def min_attack_cost(equipped: List[Dict[str, Any]]) -> int:
    """返回可用攻击技能的最低能量消耗；没有攻击技能时返回 0。"""
    min_cost = 99
    for skill in equipped:
        cost = skill.get("cost_energy")
        if cost is None:
            continue
        damage_type = skill.get("skill_damage_type", 0)
        if damage_type in (2, 3):
            min_cost = min(min_cost, cost)
    return min_cost if min_cost < 99 else 0


def equipped_or_used_skills(active_pet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """按旧逻辑从当前宠物取装备技能，缺失时回退到已使用技能。"""
    return active_pet.get("equipped_skills") or active_pet.get("used_skills") or []


def build_my_energy_messages(my_active: Dict[str, Any]) -> List[Dict[str, str]]:
    """根据我方当前能量生成能量管理提示。"""
    my_energy = my_active.get("energy", 5)
    min_cost = min_attack_cost(equipped_or_used_skills(my_active))
    if my_energy <= 1 and min_cost > 1:
        return [{
            "type": "energy_starved",
            "message": f"我方能量仅剩 {my_energy}，无法使用攻击技能，考虑能量瓶或低耗技能",
        }]
    if my_energy <= 3 and min_cost > my_energy:
        return [{
            "type": "energy_low",
            "message": f"我方能量 {my_energy} 不足以使用最强技能（需 {min_cost}）",
        }]
    return []


def build_opp_energy_messages(
    opp_active: Dict[str, Any],
    opp_energy_log: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """根据对手能量日志生成攻击窗口提示。"""
    opp_energy = opp_active.get("energy", 5)
    if opp_energy > 2 or len(opp_energy_log) < 2:
        return []

    prev_energy = opp_energy_log[-2].get("energy", 5)
    if prev_energy <= opp_energy:
        return []
    return [{
        "type": "opp_energy_low",
        "message": "对手能量可能不足，可趁机强攻",
    }]


def energy_advice_priority(messages: List[Dict[str, str]]) -> int:
    """能量建议优先级，能量枯竭为重要，其余为信息。"""
    return 1 if any(message["type"] == "energy_starved" for message in messages) else 2


def should_avoid_skill(my_active: Dict[str, Any]) -> bool:
    """判断是否应向战术引擎发出 avoid_skill 信号。"""
    my_energy = my_active.get("energy", 5)
    min_cost = min_attack_cost(equipped_or_used_skills(my_active))
    return my_energy <= 1 and min_cost > 1
