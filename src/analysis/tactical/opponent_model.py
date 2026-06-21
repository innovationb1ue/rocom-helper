"""对手行动概率模型。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from src.analysis.models import OpponentAction
from src.analysis.pet_identity import same_battle_pet
from src.analysis.skill_resolver import resolve_opponent_skills
from src.analysis.tactical import presentation, runtime
from src.data.loader import get_skill_meta
from src.game.type_chart import TypeChart

DamageFn = Callable[[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]], int]


def predict_opponent_actions(
    opp_active: Dict[str, Any],
    opp_pets: List[Dict[str, Any]],
    state: Dict[str, Any],
    *,
    chart: TypeChart,
    calc_damage: DamageFn,
) -> List[OpponentAction]:
    """预测对手可能行动及概率。"""
    actions: List[OpponentAction] = []
    opp_energy = opp_active.get("energy", 10)
    opp_skills, opp_source = resolve_opponent_skills(opp_active)

    skill_probs = compute_skill_probabilities(opp_skills, opp_energy, opp_active)
    for skill_id, prob, skill_name in skill_probs:
        meta = get_skill_meta(skill_id) or {}
        skill_runtime = runtime.skill_runtime(opp_active, skill_id)
        skill = next((s for s in opp_skills if s.get("skill_id") == skill_id), {})
        actions.append(OpponentAction(
            action_type="skill",
            skill_id=skill_id,
            skill_name=skill_name,
            probability=prob,
            source=opp_source,
            reason=opp_action_reason(skill_id, prob, opp_active),
            priority_layer=runtime.skill_priority_layer(skill, skill_runtime, meta),
        ))

    switch_prob = estimate_switch_probability(opp_active, state, chart=chart)
    if switch_prob > 0:
        living_bench = [
            p for p in opp_pets
            if p.get("current_hp", 1) > 0 and not same_battle_pet(p, opp_active)
        ]
        if living_bench:
            per_pet = switch_prob / len(living_bench)
            for pet in living_bench:
                actions.append(OpponentAction(
                    action_type="switch",
                    switch_to_name=pet.get("name", "?"),
                    probability=per_pet,
                    source="state",
                    reason="低血量或对位不利时的换宠候选",
                ))

    normalize_probabilities(actions)
    annotate_opp_threat(actions, opp_active, state, calc_damage=calc_damage)
    return actions


def resolve_opp_skills(opp_active: Dict[str, Any]) -> List[Dict[str, Any]]:
    skills, _source = resolve_opponent_skills(opp_active)
    return skills


def opp_skill_source(opp_active: Dict[str, Any]) -> str:
    _skills, source = resolve_opponent_skills(opp_active)
    return source


def compute_skill_probabilities(
    opp_skills: List[Dict[str, Any]],
    opp_energy: int,
    opp_active: Dict[str, Any],
) -> List[Tuple[int, float, str]]:
    """根据使用频率和技能威力分配技能概率。"""
    if not opp_skills:
        return []

    used_skills: Dict[int, int] = {}
    for used in (opp_active.get("used_skills") or []):
        skill_id = used.get("skill_id")
        if skill_id is not None:
            used_skills[skill_id] = used_skills.get(skill_id, 0) + 1

    entries: List[Tuple[int, float, str]] = []
    total_weight = 0.0

    for skill in opp_skills:
        skill_id = skill.get("skill_id")
        if skill_id is None:
            continue
        meta = get_skill_meta(skill_id)
        if meta is None:
            continue

        skill_runtime = runtime.skill_runtime(opp_active, skill_id)
        cd_round = runtime.skill_cd_round(skill, skill_runtime)
        if cd_round > 0:
            continue

        energy_cost = runtime.resolve_action_energy_cost(skill, skill_runtime, meta)
        if energy_cost > opp_energy:
            continue

        name = skill.get("skill_name") or meta.get("name", "?")
        freq = used_skills.get(skill_id, 0)
        if freq > 0:
            weight = float(freq)
        else:
            power = (meta.get("dam_para", [0]) or [0])[0]
            weight = max(1.0, power / 20.0)

        entries.append((skill_id, weight, name))
        total_weight += weight

    if total_weight <= 0 or not entries:
        return []

    return [(skill_id, weight / total_weight, name) for skill_id, weight, name in entries]


def estimate_switch_probability(
    opp_active: Dict[str, Any],
    state: Dict[str, Any],
    *,
    chart: TypeChart,
) -> float:
    """估算对手换宠概率。"""
    prob = 0.10

    hp_pct = opp_active.get("hp_pct", 1.0)
    if hp_pct < 0.25:
        prob = 0.25

    my_active = state.get("my_active")
    if my_active:
        my_types = my_active.get("types", [])
        opp_types = opp_active.get("types", [])
        if my_types and opp_types:
            best_mult = 0.0
            for attack_type in my_types:
                mult = chart.get_multiplier(attack_type, opp_types)
                if mult > best_mult:
                    best_mult = mult
            if best_mult >= 2.0:
                prob = max(prob, 0.35)

    return min(prob, 0.40)


def normalize_probabilities(actions: List[OpponentAction]) -> None:
    total = sum(action.probability for action in actions)
    if total <= 0:
        if not actions:
            return
        prob = 1.0 / len(actions)
        for action in actions:
            action.probability = prob
        return
    for action in actions:
        action.probability /= total


def annotate_opp_threat(
    actions: List[OpponentAction],
    opp_active: Dict[str, Any],
    state: Dict[str, Any],
    *,
    calc_damage: DamageFn,
) -> None:
    my_active = state.get("my_active")
    if not my_active:
        return
    weather = state.get("weather")
    my_hp = my_active.get("current_hp", 0)
    for action in actions:
        if action.action_type != "skill" or action.skill_id is None:
            continue
        meta = get_skill_meta(action.skill_id)
        damage = calc_damage(opp_active, my_active, meta, weather)
        action.threat_damage = damage if damage > 0 else None
        action.can_ko = damage >= my_hp if damage > 0 else False


def opp_action_reason(skill_id: int, probability: float, opp_active: Dict[str, Any]) -> str:
    return presentation.opp_action_reason(skill_id, probability, opp_active)
