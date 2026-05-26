"""Prediction reliability summaries for live battle decisions."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


_FLAG_LABELS = {
    "estimated_stats": "攻防属性来自估算",
    "uncalibrated_skill": "技能未经过回放校准",
    "multi_hit": "多段/动态连击存在波动",
    "energy_insufficient": "当前能量不足",
    "low_stat_confidence": "属性来源置信度较低",
    "calibrated": "已应用回放校准",
}


def build_prediction_reliability(
    *,
    state: Dict[str, Any],
    battle_advice: Optional[Dict[str, Any]] = None,
    tactical: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a compact reliability model for the current PvP recommendation."""
    skills = []
    opp_skills = []
    if battle_advice:
        skills = list(battle_advice.get("skill_analysis") or [])
        opp_skills = list(battle_advice.get("opp_skill_analysis") or [])

    action_unknowns: List[str] = []
    if tactical:
        for action in tactical.get("actions") or []:
            action_unknowns.extend(str(item) for item in action.get("unknowns") or [])

    flags = _collect_flags(skills + opp_skills)
    missing = _missing_reasons(state, battle_advice, action_unknowns)
    score = _score(skills, opp_skills, flags, missing)

    confidence = "high"
    if score < 55:
        confidence = "low"
    elif score < 78:
        confidence = "medium"

    return {
        "confidence": confidence,
        "score": score,
        "coverage": {
            "my_attack_predictions": _count_attack_predictions(skills),
            "opp_attack_predictions": _count_attack_predictions(opp_skills),
            "opponent_skill_source": (battle_advice or {}).get("opp_skill_source", ""),
        },
        "flags": [
            {"code": code, "label": _FLAG_LABELS.get(code, code), "count": count}
            for code, count in sorted(flags.items())
        ],
        "missing_reasons": missing,
        "context": _context_summary(state, skills + opp_skills),
    }


def _collect_flags(skills: List[Dict[str, Any]]) -> Dict[str, int]:
    flags: Dict[str, int] = {}
    for skill in skills:
        pred = skill.get("prediction") or {}
        for flag in pred.get("accuracy_flags") or []:
            flags[str(flag)] = flags.get(str(flag), 0) + 1
    return flags


def _missing_reasons(
    state: Dict[str, Any],
    battle_advice: Optional[Dict[str, Any]],
    action_unknowns: List[str],
) -> List[str]:
    reasons: List[str] = []
    opp_active = state.get("opp_active") or {}
    my_active = state.get("my_active") or {}

    if not battle_advice:
        reasons.append("当前事件没有生成伤害预测")
    elif not battle_advice.get("opp_skill_analysis"):
        reasons.append("对手技能未完全暴露，反打伤害只能估算")

    opp_source = (battle_advice or {}).get("opp_skill_source", "")
    if opp_source in {"", "preset"} and not (opp_active.get("used_skills") or []):
        reasons.append("对手尚未使用技能，概率模型依赖宠物技能池")

    if not _has_protocol_stats(opp_active):
        reasons.append("对手攻防属性不可见，使用数据表估算")
    if not _has_protocol_stats(my_active):
        reasons.append("我方攻防属性缺失，使用数据表估算")

    if state.get("weather") or (state.get("field_context") or {}).get("weather_current"):
        reasons.append("天气已参与预测，需要关注持续回合")

    for unknown in action_unknowns:
        if unknown not in reasons:
            reasons.append(unknown)

    return reasons[:6]


def _score(
    skills: List[Dict[str, Any]],
    opp_skills: List[Dict[str, Any]],
    flags: Dict[str, int],
    missing: List[str],
) -> int:
    score = 100
    if not _count_attack_predictions(skills):
        score -= 22
    if not _count_attack_predictions(opp_skills):
        score -= 14
    score -= min(24, 6 * flags.get("estimated_stats", 0))
    score -= min(18, 4 * flags.get("uncalibrated_skill", 0))
    score -= min(12, 4 * flags.get("multi_hit", 0))
    score -= min(20, 5 * len([r for r in missing if "估算" in r or "未" in r]))
    if flags.get("calibrated"):
        score += min(8, 2 * flags["calibrated"])
    return max(0, min(100, score))


def _count_attack_predictions(skills: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for skill in skills
        if skill.get("skill_damage_type") in (2, 3)
        and skill.get("expected_damage") is not None
    )


def _has_protocol_stats(pet: Dict[str, Any]) -> bool:
    stats = pet.get("stats")
    if isinstance(stats, list):
        values = [s.get("total") or s.get("calc") for s in stats if isinstance(s, dict)]
        return len([v for v in values if isinstance(v, (int, float)) and v > 0]) >= 4
    if isinstance(stats, dict):
        values = [v for v in stats.values() if isinstance(v, (int, float)) and v > 0]
        return len(values) >= 4
    return False


def _context_summary(state: Dict[str, Any], skills: List[Dict[str, Any]]) -> Dict[str, Any]:
    weather = state.get("weather") or (state.get("field_context") or {}).get("weather_current")
    uses_weather = any((skill.get("explain") or {}).get("multipliers", {}).get("weather") not in (None, 1, 1.0) for skill in skills)
    uses_hooks = any(
        any(value not in (None, False, 1, 1.0) for value in ((skill.get("explain") or {}).get("hooks") or {}).values())
        for skill in skills
    )
    return {
        "weather": weather,
        "weather_used": bool(weather or uses_weather),
        "buffs_seen": bool((state.get("my_active") or {}).get("buffs") or (state.get("opp_active") or {}).get("buffs")),
        "hooks_used": uses_hooks,
    }
