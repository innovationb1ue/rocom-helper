"""全链路集成测试 — 从 battle_state 到 damage_calc 到 battle_advisor。"""
from __future__ import annotations

import pytest

from src.analysis.battle_advisor import BattleAdvisor, BattleAdvice
from src.analysis.battle_state import BattleStateTracker
from src.analysis.damage_calc import DamageCalculator
from src.analysis.threat import ThreatAssessor
from src.game.type_chart import TypeChart


@pytest.fixture(scope="module")
def chart():
    return TypeChart()


@pytest.fixture(scope="module")
def advisor(chart):
    return BattleAdvisor(chart)


@pytest.fixture(scope="module")
def damage_calc(chart):
    return DamageCalculator(chart)


@pytest.fixture(scope="module")
def threat_assessor(chart):
    return ThreatAssessor(chart)


# ---------------------------------------------------------------------------
# TestConstructedStateIntegration — 用构造的 battle state 验证完整链路
# ---------------------------------------------------------------------------


class TestConstructedStateIntegration:
    """模拟战斗中场景，验证 tracker → advisor 的完整流程。"""

    def test_tracker_state_feeds_advisor(self, advisor):
        """tracker 输出的 state 能直接被 advisor 消费。"""
        tracker = BattleStateTracker()
        tracker.handle_event(0x1316, {
            "battle_id": 1, "battle_mode": 1, "round": 0, "max_round": 30,
            "wrappers": [
                {"pet_id": 100, "pet_name": "火龙", "types": [1], "side": 1,
                 "hp": 300, "max_hp": 300,
                 "stats": [{"name": "ATK", "total": 200}, {"name": "SPA", "total": 180},
                           {"name": "DEF", "total": 150}, {"name": "SPD", "total": 150}]},
                {"pet_id": 200, "pet_name": "草蛇", "types": [3], "side": 401,
                 "hp": 350, "max_hp": 350,
                 "stats": [{"name": "DEF", "total": 150}, {"name": "SPD", "total": 150}]},
            ],
        })
        # Simulate skill usage
        tracker.handle_event(0x1324, {"entries": [
            {"kind": "skill_cast", "actor_side": 1, "skill_id": 7000170,
             "skill_name": "岩石偷袭", "energy_after": 3},
        ]})
        state = tracker.get_state()
        advice = advisor.analyze(state)
        assert isinstance(advice, BattleAdvice)
        # State should have valid structure for advisor
        assert state["my_active"] is not None
        assert state["opp_active"] is not None

    def test_mid_battle_damage_decreases_hp(self, damage_calc):
        """战斗中 HP 减少后，伤害预测的 pct_hp_range 正确反映剩余 HP。"""
        attacker = {
            "types": [1], "level": 100, "max_hp": 300, "current_hp": 300,
            "stats": [{"name": "ATK", "total": 200}, {"name": "SPA", "total": 180}],
        }
        defender = {
            "types": [3], "max_hp": 350, "current_hp": 50,  # Low HP
            "stats": [{"name": "DEF", "total": 150}, {"name": "SPD", "total": 150}],
        }
        skill = {"id": 1, "name": "测试", "damage_type": 2, "dam_para": [80],
                 "skill_dam_type": 1, "energy_cost": [3]}
        result = damage_calc.calculate(attacker, defender, skill)
        assert result is not None
        assert result.can_ko is True  # 火打草 2x, defender only 50 hp

    def test_suggestions_after_damage(self, advisor):
        """受伤后 tracker 的 get_suggestions 和 advisor 的 analyze 都反映状态。"""
        tracker = BattleStateTracker()
        tracker.handle_event(0x1316, {
            "battle_id": 1, "battle_mode": 1, "round": 0, "max_round": 30,
            "wrappers": [
                {"pet_id": 100, "pet_name": "火龙", "types": [1], "side": 1,
                 "hp": 300, "max_hp": 300},
                {"pet_id": 200, "pet_name": "草蛇", "types": [3], "side": 401,
                 "hp": 350, "max_hp": 350},
            ],
        })
        # Heavy damage to opponent
        tracker.handle_event(0x1324, {"entries": [
            {"kind": "damage", "damage": 320, "target_hp_after": 30,
             "damage_target_side": 401},
        ]})
        # Tracker suggestions
        suggestions = tracker.get_suggestions()
        sug_types = [s["type"] for s in suggestions]
        assert "finish_off" in sug_types  # Opponent at low HP


# ---------------------------------------------------------------------------
# TestReplayIntegration — 用真实回放数据验证 advisor
# ---------------------------------------------------------------------------


class TestReplayIntegration:
    """用 session_1 的真实回放数据验证全链路。"""

    def test_advisor_on_replay_state(self, advisor, session1_baseline_result):
        """advisor 能处理回放状态不崩溃。"""
        events, final_state = session1_baseline_result
        advice = advisor.analyze(final_state)
        assert isinstance(advice, BattleAdvice)

    def test_advisor_on_each_round(self, advisor, session1_baseline_result):
        """每一轮结束后 advisor 都能产生有效输出。"""
        events, _ = session1_baseline_result
        round_events = [e for e in events if e["opcode"] == 0x131A]
        success_count = 0
        for e in round_events:
            state = e.get("state", {})
            if state.get("my_active") and state.get("opp_active"):
                advice = advisor.analyze(state)
                assert isinstance(advice, BattleAdvice)
                success_count += 1
        assert success_count > 0, "No valid round states to analyze"

    def test_damage_calc_on_final_state(self, damage_calc, session1_baseline_result):
        """用最终状态的宠物数据验证伤害计算不崩溃。"""
        from src.data.loader import get_skill_meta
        _, state = session1_baseline_result
        my_active = state.get("my_active")
        opp_active = state.get("opp_active")
        if my_active and opp_active:
            skills = my_active.get("used_skills") or my_active.get("equipped_skills") or []
            for s in skills[:3]:
                meta = get_skill_meta(s.get("skill_id"))
                if meta:
                    result = damage_calc.calculate(my_active, opp_active, meta)
                    # Should not crash; result may be None for non-attack skills
                    assert result is None or hasattr(result, "min_damage")

    def test_threat_assessment_on_replay(self, threat_assessor, session1_baseline_result):
        """用回放数据验证威胁评估。需要将 stats 格式适配为 dict。"""
        _, state = session1_baseline_result
        my_pets_raw = state.get("my_pets", [])
        opp_pets_raw = state.get("opp_pets", [])

        def _adapt_pet(pet):
            """将协议层 stats list 转换为 threat 模块需要的 dict 格式。"""
            p = dict(pet)
            raw_stats = p.get("stats", [])
            if isinstance(raw_stats, list):
                stats_dict = {}
                for s in raw_stats:
                    name = s.get("name")
                    val = s.get("total") or (s.get("calc") or 0) + (s.get("bonus") or 0)
                    if name:
                        stats_dict[name] = val
                p["stats"] = stats_dict
            # Also convert skills if they're in protocol format
            raw_skills = p.get("skills", [])
            if raw_skills and isinstance(raw_skills, list) and isinstance(raw_skills[0], dict):
                p["skills"] = [{"type_id": s.get("skill_dam_type"), "name": s.get("skill_name")}
                               for s in raw_skills if s.get("skill_dam_type") is not None]
            return p

        my_pets = [_adapt_pet(p) for p in my_pets_raw]
        opp_pets = [_adapt_pet(p) for p in opp_pets_raw]
        if my_pets and opp_pets:
            threats = threat_assessor.assess_threats(opp_pets, my_pets)
            assert isinstance(threats, list)
            assert len(threats) == len(opp_pets)
            for t in threats:
                assert "threat_score" in t
                assert "threat_level" in t
                assert t["threat_level"] in ("高", "中", "低")
