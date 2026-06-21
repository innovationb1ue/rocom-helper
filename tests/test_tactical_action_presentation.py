"""单行动战术展示文案测试。"""
from __future__ import annotations

from src.analysis.tactical import action_presentation


def test_action_category_orders_switch_ko_risk_and_pressure():
    assert action_presentation.action_category({"action_type": "switch"}, 0.0, False, 0, {"current_hp": 100}) == "switch"
    assert action_presentation.action_category({"action_type": "skill"}, 0.0, True, 0, {"current_hp": 100}) == "finisher"
    assert action_presentation.action_category({"action_type": "skill"}, 0.0, False, 80, {"current_hp": 100}) == "gamble"
    assert action_presentation.action_category({"action_type": "skill"}, 0.3, False, 0, {"current_hp": 100}) == "pressure"
    assert action_presentation.action_category({"action_type": "skill", "energy_cost": 1}, 0.1, False, 0, {"current_hp": 100}) == "conservative"


def test_expected_gain_and_risk_summary_preserve_frontend_text():
    assert action_presentation.expected_gain(
        {"action_type": "skill"},
        80,
        False,
        {"kill_line": 20},
    ) == "预计压低 80 HP，敌方剩余约 20 HP"
    assert action_presentation.risk_summary(
        {"action_type": "skill"},
        120,
        {"current_hp": 100},
        [],
    ) == "最坏情况被反杀，承受约 120 伤害"


def test_action_unknowns_and_confidence_follow_information_quality():
    action = {"action_type": "skill", "is_damage_skill": True, "meta": {"desc": "天气强化"}}
    opp = {"stats": {}, "used_skills": []}

    unknowns = action_presentation.action_unknowns(action, opp, {})

    assert len(unknowns) >= 2
    assert action_presentation.action_confidence(unknowns, opp, lambda _opp: "high") == "low"
    assert action_presentation.action_confidence([], opp, lambda _opp: "high") == "high"


def test_has_visible_combat_stats_accepts_dict_or_list_stats():
    assert action_presentation.has_visible_combat_stats({"stats": {"atk": 1, "def": 1, "matk": 1, "mdef": 1}})
    assert action_presentation.has_visible_combat_stats({"stats": [{"total": 1}, {"total": 1}, {"total": 1}, {"total": 1}]})
    assert not action_presentation.has_visible_combat_stats({"stats": {}})
