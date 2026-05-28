"""战术推荐的展示分类与解释文案。

TacticalEngine 负责枚举和评分行动；本模块只负责把评分结果转成前端可读
的类别、收益、风险和提示，避免核心结算逻辑里混入大量 UI 文案规则。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from src.analysis.models import ActionScore, OpponentAction


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

    stats = opp_active.get("stats")
    has_stats = False
    if isinstance(stats, list):
        has_stats = len([s for s in stats if isinstance(s, dict) and (s.get("total") or 0) > 0]) >= 4
    elif isinstance(stats, dict):
        has_stats = len([v for v in stats.values() if isinstance(v, (int, float)) and v > 0]) >= 4
    if not has_stats:
        unknowns.append("对手攻防属性不可见，伤害使用估算")

    if our_action["action_type"] == "skill" and our_action.get("is_damage_skill") and not state.get("weather"):
        meta = our_action.get("meta") or {}
        if "天气" in str(meta.get("desc", "")):
            unknowns.append("技能可能受天气/场地影响，当前仅按已知场地计算")
    return unknowns


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


def primary_plan(actions: List[ActionScore]) -> str:
    if not actions:
        return ""
    top = actions[0]
    name = f"换上 {top.switch_to_name}" if top.action_type == "switch" else (top.skill_name or top.reason)
    return f"首选 {name}：{top.expected_gain or top.reason}"


def build_warnings(
    actions: List[ActionScore],
    opp_predicted: List[OpponentAction],
    confidence: str,
    opp_skill_source: str,
) -> List[str]:
    warnings: List[str] = []
    if confidence == "low" or opp_skill_source in {"", "preset"}:
        warnings.append("对手技能信息不足，推荐偏保守")
    dangerous = [a for a in opp_predicted if a.can_ko]
    if dangerous:
        names = "、".join(a.skill_name or a.switch_to_name or "未知行动" for a in dangerous[:2])
        warnings.append(f"对手存在击杀威胁：{names}")
    if actions and actions[0].category == "gamble":
        warnings.append("首选行动属于高风险收益线，需确认是否愿意赌对手行动")
    return warnings


def opponent_profile(
    opp_active: Dict[str, Any],
    opp_predicted: List[OpponentAction],
    opp_skill_source: str,
) -> Dict[str, Any]:
    used = opp_active.get("used_skills") or []
    switch_prob = sum(a.probability for a in opp_predicted if a.action_type == "switch")
    skill_prob = sum(a.probability for a in opp_predicted if a.action_type == "skill")
    return {
        "skill_source": opp_skill_source,
        "revealed_skills": [
            {"skill_id": s.get("skill_id"), "skill_name": s.get("skill_name")}
            for s in used
        ],
        "revealed_skill_count": len(used),
        "estimated_switch_probability": round(switch_prob, 3),
        "estimated_skill_probability": round(skill_prob, 3),
        "low_hp": opp_active.get("hp_pct", 1.0) < 0.25,
        "low_energy": opp_active.get("energy", 10) <= 1,
    }


def opp_action_reason(skill_id: int, probability: float, opp_active: Dict[str, Any]) -> str:
    used = {
        s.get("skill_id")
        for s in (opp_active.get("used_skills") or [])
    }
    if skill_id in used:
        return f"已使用过，按历史频率估计 {probability:.0%}"
    return f"来自候选技能池，按威力/能量估计 {probability:.0%}"
