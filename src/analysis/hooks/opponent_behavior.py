"""对手行为追踪纯规则 — 供 OpponentTrackerHook 和单元测试复用。"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


SkillCounts = Dict[str, Counter]
SwitchLog = List[Dict[str, Any]]
SwitchKey = Optional[Tuple[int, str]]


def is_my_side(side_val: Any) -> bool:
    """按旧 hook 口径判断 actor_side 是否为我方。"""
    if isinstance(side_val, str):
        return side_val == "我方"
    return 1 <= int(side_val) <= 6 if side_val is not None else False


def record_skill_casts(
    entries: List[Dict[str, Any]],
    opp_active: Dict[str, Any],
    skill_counts: SkillCounts,
) -> None:
    """把 entries 中的对手技能施放累计到 skill_counts。"""
    pet_name = opp_active.get("name", "未知")
    for entry in entries:
        if entry.get("kind") != "skill_cast":
            continue
        if is_my_side(entry.get("actor_side", "")):
            continue

        skill_name = entry.get("skill_name", "?")
        if pet_name not in skill_counts:
            skill_counts[pet_name] = Counter()
        skill_counts[pet_name][skill_name] += 1


def skill_preference_messages(skill_counts: SkillCounts) -> List[Dict[str, str]]:
    """根据技能计数生成偏好技能提示。"""
    messages: List[Dict[str, str]] = []
    for pet_name, counts in skill_counts.items():
        total_uses = sum(counts.values())
        if total_uses < 3:
            continue
        top_skill, top_count = counts.most_common(1)[0]
        ratio = top_count / total_uses
        if top_count >= 2 and ratio >= 0.5:
            messages.append({
                "type": "skill_preference",
                "message": f"对手 {pet_name} 偏好使用 {top_skill} ({top_count}/{total_uses}次)",
            })
    return messages


def append_switch_logs(
    entries: List[Dict[str, Any]],
    switch_log: SwitchLog,
    last_switch_key: SwitchKey,
    round_num: int,
    opp_active: Dict[str, Any],
) -> SwitchKey:
    """按 round+new_pet 去重追加换宠日志，返回新的 last_switch_key。"""
    current_key = last_switch_key
    for entry in entries:
        if entry.get("kind") != "change_pet":
            continue
        new_name = entry.get("new_pet_name", "?")
        key = (round_num, new_name)
        if key == current_key:
            continue

        hp_pct = opp_active.get("hp_pct", 1.0)
        switch_log.append({
            "round": round_num,
            "new_pet": new_name,
            "prev_hp_pct": round(hp_pct, 2),
        })
        current_key = key
    return current_key


def switch_pattern_messages(switch_log: SwitchLog) -> List[Dict[str, str]]:
    """根据换宠日志生成低血换宠模式提示。"""
    if len(switch_log) < 2:
        return []

    low_hp_switches = sum(
        1 for entry in switch_log if entry["prev_hp_pct"] < 0.4
    )
    if low_hp_switches < 2:
        return []
    return [{
        "type": "switch_pattern",
        "message": "对手倾向在HP较低时换宠",
    }]


def build_behavior_messages(
    entries: List[Dict[str, Any]],
    opp_active: Dict[str, Any],
    skill_counts: SkillCounts,
    switch_log: SwitchLog,
) -> List[Dict[str, str]]:
    """记录本次行动并生成当前可提示的行为分析消息。"""
    record_skill_casts(entries, opp_active, skill_counts)
    messages = skill_preference_messages(skill_counts)
    messages.extend(switch_pattern_messages(switch_log))
    return messages


def build_behavior_data(
    skill_counts: SkillCounts,
    switch_log: SwitchLog,
    total_rounds: int,
) -> Dict[str, Any]:
    """构造 HookAdvice data payload，保持旧字段形状。"""
    return {
        "skill_history": {
            pet_name: dict(counts)
            for pet_name, counts in skill_counts.items()
        },
        "switch_log": switch_log,
        "total_rounds": total_rounds,
    }
