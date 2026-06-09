"""单个战术行动的展示分类、收益、风险和置信度。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List


def action_category(
    our_action: Dict[str, Any],
    score: float,
    can_ko: bool,
    damage_taken: int,
    my_active: Dict[str, Any],
) -> str:
    if our_action["action_type"] == "switch":
        return "switch"
    if can_ko:
        return "finisher"
    if damage_taken >= my_active.get("current_hp", 0) * 0.8:
        return "gamble"
    if score >= 0.28:
        return "pressure"
    if our_action.get("energy_cost", 0) <= 1:
        return "conservative"
    return "balanced"


def expected_gain(
    our_action: Dict[str, Any],
    damage_dealt: int,
    can_ko: bool,
    metrics: Dict[str, Any],
) -> str:
    if our_action["action_type"] == "switch":
        return f"换入后对位倍率 x{metrics.get('type_matchup', 1.0)}，剩余生存线 {metrics.get('survival_line', 0)}"
    if can_ko:
        return "本回合有击杀线，成功后取得宠物数优势"
    if damage_dealt > 0:
        return f"预计压低 {damage_dealt} HP，敌方剩余约 {metrics.get('kill_line', 0)} HP"
    return "获得状态收益，主要价值在后续回合"


def risk_summary(
    our_action: Dict[str, Any],
    damage_taken: int,
    my_active: Dict[str, Any],
    unknowns: List[str],
) -> str:
    if damage_taken >= my_active.get("current_hp", 0):
        return f"最坏情况被反杀，承受约 {damage_taken} 伤害"
    if damage_taken > 0:
        return f"最坏情况承受约 {damage_taken} 伤害"
    if our_action["action_type"] == "switch":
        return "若对手读换宠，可能被克制技能惩罚"
    if unknowns:
        return "主要风险来自对手技能或属性估算不完整"
    return "短期风险较低"


def action_unknowns(
    our_action: Dict[str, Any],
    opp_active: Dict[str, Any],
    state: Dict[str, Any],
) -> List[str]:
    unknowns: List[str] = []
    if not (opp_active.get("equipped_skills") or opp_active.get("skills") or opp_active.get("used_skills")):
        unknowns.append("对手技能未暴露，使用技能池估算")
    elif not (opp_active.get("equipped_skills") or opp_active.get("skills")):
        unknowns.append("对手只暴露了部分已使用技能")

    if not has_visible_combat_stats(opp_active):
        unknowns.append("对手攻防属性不可见，伤害使用估算")

    if our_action["action_type"] == "skill" and our_action.get("is_damage_skill") and not state.get("weather"):
        meta = our_action.get("meta") or {}
        if "天气" in str(meta.get("desc", "")):
            unknowns.append("技能可能受天气/场地影响，当前仅按已知场地计算")
    return unknowns


def has_visible_combat_stats(pet: Dict[str, Any]) -> bool:
    stats = pet.get("stats")
    if isinstance(stats, list):
        return len([s for s in stats if isinstance(s, dict) and (s.get("total") or 0) > 0]) >= 4
    if isinstance(stats, dict):
        return len([v for v in stats.values() if isinstance(v, (int, float)) and v > 0]) >= 4
    return False


def action_confidence(
    unknowns: List[str],
    opp_active: Dict[str, Any],
    fallback: Callable[[Dict[str, Any]], str],
) -> str:
    if len(unknowns) >= 2:
        return "low"
    if unknowns:
        return "medium"
    return fallback(opp_active)
