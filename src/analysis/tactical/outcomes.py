"""战术行动对撞的 outcome 推演。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from src.analysis.models import OpponentAction, ResolvedOutcome
from src.data.loader import get_skill_meta

CalcDamageFn = Callable[[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]], int]
TypeMatchupFn = Callable[[Dict[str, Any], Dict[str, Any]], float]
SwitchTargetFn = Callable[[OpponentAction, List[Dict[str, Any]], Dict[str, Any]], Optional[Dict[str, Any]]]


def resolve_outcome(
    our_action: Dict[str, Any],
    opp_action: OpponentAction,
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    my_pets: List[Dict[str, Any]],
    opp_pets: List[Dict[str, Any]],
    state: Dict[str, Any],
    *,
    calc_damage: CalcDamageFn,
    type_matchup_score: TypeMatchupFn,
    most_likely_switch_target: SwitchTargetFn,
) -> ResolvedOutcome:
    weather = state.get("weather")

    if our_action["action_type"] == "switch":
        return resolve_switch_outcome(
            our_action,
            opp_action,
            my_active,
            opp_active,
            state,
            weather,
            calc_damage=calc_damage,
            type_matchup_score=type_matchup_score,
        )

    if opp_action.action_type == "switch":
        return resolve_opp_switch_outcome(
            our_action,
            opp_action,
            my_active,
            opp_active,
            opp_pets,
            state,
            weather,
            calc_damage=calc_damage,
            type_matchup_score=type_matchup_score,
            most_likely_switch_target=most_likely_switch_target,
        )

    return resolve_skill_vs_skill(
        our_action,
        opp_action,
        my_active,
        opp_active,
        state,
        weather,
        calc_damage=calc_damage,
        type_matchup_score=type_matchup_score,
    )


def resolve_skill_vs_skill(
    our_action: Dict[str, Any],
    opp_action: OpponentAction,
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    state: Dict[str, Any],
    weather: Optional[Dict[str, Any]],
    *,
    calc_damage: CalcDamageFn,
    type_matchup_score: TypeMatchupFn,
) -> ResolvedOutcome:
    our_speed = my_active.get("effective_speed") or my_active.get("base_speed", 0)
    opp_speed = opp_active.get("effective_speed") or opp_active.get("base_speed", 0)
    our_priority = int(our_action.get("priority_layer") or 0)
    opp_priority = int(opp_action.priority_layer or 0)
    if our_priority != opp_priority:
        we_act_first = our_priority > opp_priority
    else:
        we_act_first = our_speed >= opp_speed

    our_meta = our_action.get("meta")
    our_damage = calc_damage(my_active, opp_active, our_meta, weather)

    opp_meta = get_skill_meta(opp_action.skill_id) if opp_action.skill_id else None
    opp_damage = calc_damage(opp_active, my_active, opp_meta, weather)

    our_hp = my_active.get("current_hp", 0)
    opp_hp = opp_active.get("current_hp", 0)

    we_ko = False
    opp_kos_us = False

    if we_act_first:
        opp_hp -= our_damage
        we_ko = opp_hp <= 0
        if not we_ko:
            our_hp -= opp_damage
            opp_kos_us = our_hp <= 0
    else:
        our_hp -= opp_damage
        opp_kos_us = our_hp <= 0
        if not opp_kos_us:
            opp_hp -= our_damage
            we_ko = opp_hp <= 0

    energy_after = my_active.get("energy", 10) - our_action.get("energy_cost", 0)

    return ResolvedOutcome(
        our_damage_dealt=our_damage,
        opp_damage_dealt=opp_damage if not we_ko else 0,
        we_ko=we_ko,
        opp_kos_us=opp_kos_us,
        we_act_first=we_act_first,
        our_remaining_hp=max(0, our_hp),
        opp_remaining_hp=max(0, opp_hp),
        type_matchup_after=type_matchup_score(my_active, opp_active),
        energy_after=max(0, energy_after),
        pet_count_delta=(1 if we_ko else 0) - (1 if opp_kos_us else 0),
    )


def resolve_switch_outcome(
    our_action: Dict[str, Any],
    opp_action: OpponentAction,
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    state: Dict[str, Any],
    weather: Optional[Dict[str, Any]],
    *,
    calc_damage: CalcDamageFn,
    type_matchup_score: TypeMatchupFn,
) -> ResolvedOutcome:
    """我方换宠：先手换出，对手技能打在新宠物上。"""
    incoming = our_action.get("switch_to_pet", {})

    opp_meta = get_skill_meta(opp_action.skill_id) if opp_action.skill_id else None
    opp_damage = calc_damage(opp_active, incoming, opp_meta, weather)

    our_remaining = incoming.get("current_hp", 0) - opp_damage

    return ResolvedOutcome(
        our_damage_dealt=0,
        opp_damage_dealt=opp_damage,
        we_ko=False,
        opp_kos_us=our_remaining <= 0,
        we_act_first=True,
        our_remaining_hp=max(0, our_remaining),
        opp_remaining_hp=opp_active.get("current_hp", 0),
        type_matchup_after=type_matchup_score(incoming, opp_active),
        energy_after=incoming.get("energy", 10),
        pet_count_delta=-1 if our_remaining <= 0 else 0,
        incoming_energy=incoming.get("energy", 10),
        incoming_has_buffs=bool(incoming.get("buffs")),
    )


def resolve_opp_switch_outcome(
    our_action: Dict[str, Any],
    opp_action: OpponentAction,
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    opp_pets: List[Dict[str, Any]],
    state: Dict[str, Any],
    weather: Optional[Dict[str, Any]],
    *,
    calc_damage: CalcDamageFn,
    type_matchup_score: TypeMatchupFn,
    most_likely_switch_target: SwitchTargetFn,
) -> ResolvedOutcome:
    """对手换宠：用对手最可能换上的宠物（按属性优势选）。"""
    target = most_likely_switch_target(opp_action, opp_pets, my_active)
    if target is None:
        target = opp_active

    our_meta = our_action.get("meta")
    our_damage = calc_damage(my_active, target, our_meta, weather)

    target_hp = target.get("current_hp", 0) - our_damage
    we_ko = target_hp <= 0

    energy_after = my_active.get("energy", 10) - our_action.get("energy_cost", 0)

    return ResolvedOutcome(
        our_damage_dealt=our_damage,
        opp_damage_dealt=0,
        we_ko=we_ko,
        opp_kos_us=False,
        we_act_first=True,
        our_remaining_hp=my_active.get("current_hp", 0),
        opp_remaining_hp=max(0, target_hp),
        type_matchup_after=type_matchup_score(my_active, target),
        energy_after=max(0, energy_after),
        pet_count_delta=1 if we_ko else 0,
    )
