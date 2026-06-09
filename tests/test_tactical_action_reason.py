"""战术行动推荐理由测试。"""
from __future__ import annotations

from src.analysis.tactical import action_reason


def test_switch_reason_mentions_incoming_damage_and_matchup():
    assert action_reason.generate_reason(
        {"action_type": "switch", "switch_to_name": "海豹船长"},
        damage_dealt=0,
        damage_taken=42,
        can_ko=False,
    ) == "换上 海豹船长，吃 42 伤害，改善对位"


def test_skill_reason_marks_high_damage_energy_and_incoming_damage():
    assert action_reason.generate_reason(
        {"action_type": "skill", "skill_name": "强攻", "energy_cost": 5},
        damage_dealt=180,
        damage_taken=30,
        can_ko=True,
    ) == "强攻：先手击杀，高伤害，耗能 5，承受 30"


def test_skill_reason_falls_back_to_skill_name_without_signals():
    assert action_reason.generate_reason(
        {"action_type": "skill", "skill_name": "等待", "energy_cost": 0},
        damage_dealt=0,
        damage_taken=0,
        can_ko=False,
    ) == "等待"
