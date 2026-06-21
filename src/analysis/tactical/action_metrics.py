"""战术行动 cockpit metrics 构造。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

TypeMatchupFn = Callable[[Dict[str, Any], Dict[str, Any]], float]


def action_metrics(
    *,
    our_action: Dict[str, Any],
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    damage_dealt: int,
    damage_taken: int,
    can_ko: bool,
    type_matchup_score: TypeMatchupFn,
) -> Dict[str, Any]:
    """构造单行动 cockpit 指标。"""
    my_speed = active_speed(my_active)
    opp_speed = active_speed(opp_active)
    priority_layer = int(our_action.get("priority_layer") or 0)
    energy_after = max(0, my_active.get("energy", 10) - our_action.get("energy_cost", 0))
    my_hp = my_active.get("current_hp", 0)
    opp_hp = opp_active.get("current_hp", 0)
    return {
        "speed_order": speed_order(my_speed, opp_speed, priority_layer),
        "my_speed": my_speed,
        "opp_speed": opp_speed,
        "priority_layer": priority_layer,
        "energy_after": energy_after,
        "kill_line": max(0, opp_hp - max(0, damage_dealt)),
        "survival_line": max(0, my_hp - max(0, damage_taken)),
        "damage_pct": round(damage_dealt / max(1, opp_active.get("max_hp", 1)), 3) if damage_dealt else 0,
        "incoming_pct": round(damage_taken / max(1, my_active.get("max_hp", 1)), 3) if damage_taken else 0,
        "can_ko": can_ko,
        "switch_penalty": our_action["action_type"] == "switch" and damage_taken > 0,
        "type_matchup": type_matchup_score(our_action.get("switch_to_pet", my_active), opp_active),
    }


def battle_metrics(
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    my_pets: List[Dict[str, Any]],
    opp_pets: List[Dict[str, Any]],
    *,
    type_matchup_score: TypeMatchupFn,
) -> Dict[str, Any]:
    """构造整场战术 cockpit 指标。"""
    living_my = [p for p in my_pets if p.get("current_hp", 1) > 0]
    living_opp = [p for p in opp_pets if p.get("current_hp", 1) > 0]
    my_speed = active_speed(my_active)
    opp_speed = active_speed(opp_active)
    return {
        "speed_line": {
            "my": my_speed,
            "opp": opp_speed,
            "order": battle_speed_order(my_speed, opp_speed),
        },
        "energy_window": {
            "my": my_active.get("energy", 0),
            "opp": opp_active.get("energy", 0),
        },
        "pet_count": {
            "my_alive": len(living_my),
            "opp_alive": len(living_opp),
            "delta": len(living_my) - len(living_opp),
        },
        "type_matchup": type_matchup_score(my_active, opp_active),
    }


def active_speed(pet: Dict[str, Any]) -> Optional[int]:
    return pet.get("effective_speed") or pet.get("base_speed")


def speed_order(my_speed: Optional[int], opp_speed: Optional[int], priority_layer: int) -> str:
    if priority_layer > 0:
        return f"先手技能 +{priority_layer}"
    if priority_layer < 0:
        return f"后发技能 {priority_layer}"
    if my_speed is None or opp_speed is None:
        return "速度未知"
    return "速度更快" if my_speed >= opp_speed else "速度较慢"


def battle_speed_order(my_speed: Optional[int], opp_speed: Optional[int]) -> str:
    if my_speed is None or opp_speed is None:
        return "速度未知"
    return "我方先手" if my_speed >= opp_speed else "对手先手"
