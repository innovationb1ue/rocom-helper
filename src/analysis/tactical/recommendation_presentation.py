"""整条战术推荐的展示摘要、警告和对手画像。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.analysis.models import ActionScore, OpponentAction


def primary_plan(actions: List[ActionScore]) -> str:
    if not actions:
        return ""
    top = actions[0]
    name = f"换上 {top.switch_to_name}" if top.action_type == "switch" else (top.skill_name or top.reason)
    if top.confidence == "low":
        return f"待确认候选 {name}：{top.expected_gain or top.reason}"
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
