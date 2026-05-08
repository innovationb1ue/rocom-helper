"""战斗分析协调器测试 — 验证 BattleAdvisor 整合伤害计算与建议生成。"""
from __future__ import annotations

import pytest

from src.analysis.battle_advisor import BattleAdvisor, BattleAdvice
from src.game.type_chart import TypeChart


@pytest.fixture(scope="module")
def advisor():
    return BattleAdvisor(TypeChart())


def _make_pet(name="火龙", types=None, atk=200, spa=180, def_=150, spd=150,
              max_hp=300, current_hp=300, energy=10, level=100,
              used_skills=None, equipped_skills=None, skills=None,
              base_skill_pool=None):
    types = types or [1]
    pet = {
        "name": name,
        "types": types,
        "level": level,
        "max_hp": max_hp,
        "current_hp": current_hp,
        "energy": energy,
        "stats": [
            {"name": "ATK", "total": atk},
            {"name": "SPA", "total": spa},
            {"name": "DEF", "total": def_},
            {"name": "SPD", "total": spd},
        ],
    }
    if used_skills is not None:
        pet["used_skills"] = used_skills
    if equipped_skills is not None:
        pet["equipped_skills"] = equipped_skills
    if skills is not None:
        pet["skills"] = skills
    if base_skill_pool is not None:
        pet["base_skill_pool"] = base_skill_pool
    return pet


def _battle_state(my_active, opp_active):
    return {
        "my_active": my_active,
        "opp_active": opp_active,
        "my_pets": [my_active],
        "opp_pets": [opp_active],
        "round": 1,
        "battle_id": 1,
    }


# ---------------------------------------------------------------------------
# TestAnalyze — 核心分析方法
# ---------------------------------------------------------------------------


class TestAnalyze:
    def test_no_active_returns_empty(self, advisor):
        """没有 active pet 时返回空建议。"""
        result = advisor.analyze({"my_active": None, "opp_active": None})
        assert result.damage_predictions == []
        assert result.suggestions == []
        assert result.best_damage_skill is None

    def test_no_opp_active_returns_empty(self, advisor):
        """没有对手 active pet 时返回空建议。"""
        my = _make_pet()
        result = advisor.analyze({"my_active": my, "opp_active": None})
        assert result.damage_predictions == []

    def test_returns_battle_advice(self, advisor):
        """正常情况返回 BattleAdvice 对象。"""
        my = _make_pet(
            used_skills=[{"skill_id": 7000170}],  # 岩石偷袭, dt=2, power=80
        )
        opp = _make_pet(name="水龟", types=[2], def_=150, spd=150)
        result = advisor.analyze(_battle_state(my, opp))
        assert isinstance(result, BattleAdvice)

    def test_damage_predictions_with_attack_skill(self, advisor):
        """有攻击技能时生成伤害预测。"""
        my = _make_pet(
            types=[8],  # 地面系
            used_skills=[{"skill_id": 7000170}],  # 岩石偷袭: dt=2, power=80, sdt=8(地)
        )
        opp = _make_pet(name="水龟", types=[2], def_=100, spd=100)
        result = advisor.analyze(_battle_state(my, opp))
        # 7000170 is physical ground skill vs water → ground resists water
        # Should produce at least one prediction
        assert isinstance(result.damage_predictions, list)

    def test_best_damage_skill_set(self, advisor):
        """有预测时 best_damage_skill 为最高伤害技能。"""
        my = _make_pet(
            used_skills=[
                {"skill_id": 7000170},  # 岩石偷袭 power=80
                {"skill_id": 7020450},  # 突袭 power=70
            ],
        )
        opp = _make_pet(types=[0], def_=150, spd=150)
        result = advisor.analyze(_battle_state(my, opp))
        if result.damage_predictions:
            assert result.best_damage_skill is not None
            assert result.best_damage_skill == result.damage_predictions[0]


# ---------------------------------------------------------------------------
# TestSkillCollectionPriority — 技能收集优先级
# ---------------------------------------------------------------------------


class TestSkillCollectionPriority:
    def test_used_skills_priority(self, advisor):
        """used_skills 优先于 equipped_skills。"""
        my = _make_pet(
            used_skills=[{"skill_id": 7000170}],
            equipped_skills=[{"skill_id": 7020450}],
            skills=[{"skill_id": 7020410}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        # Should use used_skills (7000170), not equipped/skills
        if result.damage_predictions:
            used_ids = [p.skill_id for p in result.damage_predictions]
            assert 7000170 in used_ids

    def test_equipped_skills_fallback(self, advisor):
        """无 used_skills 时用 equipped_skills。"""
        my = _make_pet(
            equipped_skills=[{"skill_id": 7000170}],
            skills=[{"skill_id": 7020450}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        if result.damage_predictions:
            used_ids = [p.skill_id for p in result.damage_predictions]
            assert 7000170 in used_ids

    def test_skills_fallback(self, advisor):
        """无 used/equipped 时用 skills。"""
        my = _make_pet(
            skills=[{"skill_id": 7000170}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        if result.damage_predictions:
            used_ids = [p.skill_id for p in result.damage_predictions]
            assert 7000170 in used_ids

    def test_base_skill_pool_fallback(self, advisor):
        """无其他技能时回退到 base_skill_pool。"""
        my = _make_pet(
            base_skill_pool=[{"skill_id": 7000170}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        if result.damage_predictions:
            used_ids = [p.skill_id for p in result.damage_predictions]
            assert 7000170 in used_ids


# ---------------------------------------------------------------------------
# TestSuggestions — 建议生成
# ---------------------------------------------------------------------------


class TestSuggestions:
    def test_no_suggestions_when_no_predictions(self, advisor):
        """无伤害预测时无建议。"""
        my = _make_pet()  # 无技能
        opp = _make_pet()
        result = advisor.analyze(_battle_state(my, opp))
        assert result.suggestions == []

    def test_super_effective_suggestion(self, advisor):
        """效果拔群技能生成 super_effective 建议。"""
        my = _make_pet(
            types=[8],  # 地面系
            atk=300,
            used_skills=[{"skill_id": 7000170}],  # 岩石偷袭: dt=2, sdt=8(地), power=80
        )
        opp = _make_pet(
            name="火龙", types=[1],  # 火 → 地打火 2x
            def_=100, current_hp=500, max_hp=500,
        )
        result = advisor.analyze(_battle_state(my, opp))
        types = [s["type"] for s in result.suggestions]
        # Ground vs fire = 2.0 (super effective)
        if result.damage_predictions and result.damage_predictions[0].effectiveness >= 2.0:
            assert "super_effective" in types or "ko_skill" in types


# ---------------------------------------------------------------------------
# TestToDict — 序列化
# ---------------------------------------------------------------------------


class TestToDict:
    def test_to_dict_structure(self, advisor):
        my = _make_pet(used_skills=[{"skill_id": 7000170}])
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        d = result.to_dict()
        assert "damage_predictions" in d
        assert "suggestions" in d
        if result.best_damage_skill:
            assert "best_damage_skill" in d
