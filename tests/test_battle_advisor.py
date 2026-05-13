"""战斗分析协调器测试 — 验证 BattleAdvisor 整合技能分析与建议生成。"""
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
              base_skill_pool=None, buffs=None):
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
    if buffs is not None:
        pet["buffs"] = buffs
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
        assert result.skill_analysis == []
        assert result.suggestions == []

    def test_no_opp_active_returns_empty(self, advisor):
        """没有对手 active pet 时返回空建议。"""
        my = _make_pet()
        result = advisor.analyze({"my_active": my, "opp_active": None})
        assert result.skill_analysis == []

    def test_returns_battle_advice(self, advisor):
        """正常情况返回 BattleAdvice 对象。"""
        my = _make_pet(
            used_skills=[{"skill_id": 7000170}],
        )
        opp = _make_pet(name="水龟", types=[2], def_=150, spd=150)
        result = advisor.analyze(_battle_state(my, opp))
        assert isinstance(result, BattleAdvice)

    def test_skill_analysis_with_attack_skill(self, advisor):
        """有攻击技能时生成 skill_analysis。"""
        my = _make_pet(
            types=[8],
            used_skills=[{"skill_id": 7000170}],
        )
        opp = _make_pet(name="水龟", types=[2], def_=100, spd=100)
        result = advisor.analyze(_battle_state(my, opp))
        assert isinstance(result.skill_analysis, list)
        attack_skills = [s for s in result.skill_analysis if s.min_damage is not None]
        assert len(attack_skills) >= 1

    def test_skill_analysis_sorted_by_slot(self, advisor):
        """skill_analysis 应按 equipped_slot 排序。"""
        my = _make_pet(
            used_skills=[
                {"skill_id": 7000170},
                {"skill_id": 7020450},
            ],
        )
        opp = _make_pet(types=[0], def_=150, spd=150)
        result = advisor.analyze(_battle_state(my, opp))
        slots = [s.equipped_slot for s in result.skill_analysis]
        assert slots == sorted(slots)


# ---------------------------------------------------------------------------
# TestSkillCollectionPriority — 技能收集优先级
# ---------------------------------------------------------------------------


class TestSkillCollectionPriority:
    def test_equipped_skills_priority(self, advisor):
        """equipped_skills 优先于 used_skills 和 skills。"""
        my = _make_pet(
            equipped_skills=[{"skill_id": 7000170}],
            used_skills=[{"skill_id": 7020450}],
            skills=[{"skill_id": 7020410}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        used_ids = [s.skill_id for s in result.skill_analysis]
        assert 7000170 in used_ids

    def test_skills_fallback(self, advisor):
        """无 equipped_skills 时用 skills。"""
        my = _make_pet(
            skills=[{"skill_id": 7000170}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        used_ids = [s.skill_id for s in result.skill_analysis]
        assert 7000170 in used_ids

    def test_used_skills_as_fallback(self, advisor):
        """无 equipped/skills 时用 used_skills。"""
        my = _make_pet(
            used_skills=[{"skill_id": 7000170}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        used_ids = [s.skill_id for s in result.skill_analysis]
        assert 7000170 in used_ids

    def test_intermediate_round_shows_all_equipped(self, advisor):
        """中间回合：equipped_skills 有4个技能，used_skills 只有部分。"""
        my = _make_pet(
            equipped_skills=[
                {"skill_id": 7000170, "equipped_slot": 1},
                {"skill_id": 7020450, "equipped_slot": 2},
                {"skill_id": 7020410, "equipped_slot": 3},
                {"skill_id": 7020430, "equipped_slot": 4},
            ],
            used_skills=[
                {"skill_id": 7000170},
            ],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        assert len(result.skill_analysis) == 4
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        used_ids = [s.skill_id for s in result.skill_analysis]
        assert 7000170 in used_ids

    def test_base_skill_pool_fallback(self, advisor):
        """无其他技能时回退到 base_skill_pool。"""
        my = _make_pet(
            base_skill_pool=[{"skill_id": 7000170}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        used_ids = [s.skill_id for s in result.skill_analysis]
        assert 7000170 in used_ids


# ---------------------------------------------------------------------------
# TestSuggestions — 建议生成
# ---------------------------------------------------------------------------


class TestSuggestions:
    def test_no_suggestions_when_no_predictions(self, advisor):
        """无技能时无建议。"""
        my = _make_pet()
        opp = _make_pet()
        result = advisor.analyze(_battle_state(my, opp))
        assert result.suggestions == []

    def test_super_effective_suggestion(self, advisor):
        """效果拔群技能生成 super_effective 建议。"""
        my = _make_pet(
            types=[8],
            atk=300,
            used_skills=[{"skill_id": 7000170}],
        )
        opp = _make_pet(
            name="火龙", types=[1],
            def_=100, current_hp=500, max_hp=500,
        )
        result = advisor.analyze(_battle_state(my, opp))
        types = [s["type"] for s in result.suggestions]
        attack_skills = [s for s in result.skill_analysis if s.effectiveness is not None]
        if attack_skills and attack_skills[0].effectiveness >= 2.0:
            assert "super_effective" in types or "ko_skill" in types


# ---------------------------------------------------------------------------
# TestToDict — 序列化
# ---------------------------------------------------------------------------


class TestTraits:
    def test_no_traits_when_no_buffs(self, advisor):
        """无 buffs 且不在 wiki 数据中时 traits 为空。"""
        my = _make_pet(used_skills=[{"skill_id": 7000170}])
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        assert result.traits == []

    def test_traits_extracted_from_innate_buffs(self, advisor):
        """先天 buff 提取为 traits。"""
        my = _make_pet(
            used_skills=[{"skill_id": 7000170}],
            buffs=[{"id": 20410080}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        names = [t["name"] for t in result.traits]
        assert "临界防御" in names

    def test_non_innate_buffs_not_in_traits(self, advisor):
        """非先天 buff 不出现在 traits。"""
        my = _make_pet(
            used_skills=[{"skill_id": 7000170}],
            buffs=[{"id": 99999999}, {"id": 20410080}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        assert len(result.traits) == 1
        assert result.traits[0]["name"] == "临界防御"

    def test_wiki_pet_trait_lookup(self, advisor):
        """wiki 数据中精灵名的特性能正确查找。"""
        my = _make_pet(
            name="厉毒修萝",
            used_skills=[{"skill_id": 7000170}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        names = [t["name"] for t in result.traits]
        assert "侵蚀" in names

    def test_wiki_pet_trait_not_contaminated_by_buffs(self, advisor):
        """wiki 特性 + 战斗效果 buff 不应产生多余 traits。"""
        my = _make_pet(
            name="厉毒修萝",
            used_skills=[{"skill_id": 7000170}],
            buffs=[
                {"id": 2091009, "name": "侵蚀"},
                {"id": 2108015, "name": "仅精灵连击数+1"},
            ],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        names = [t["name"] for t in result.traits]
        assert names == ["侵蚀"]

    def test_fire_god_trait(self, advisor):
        """火神的特性 '助燃' 能正确查找。"""
        my = _make_pet(
            name="火神",
            used_skills=[{"skill_id": 7000170}],
        )
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        names = [t["name"] for t in result.traits]
        assert "助燃" in names


class TestToDict:
    def test_to_dict_structure(self, advisor):
        my = _make_pet(used_skills=[{"skill_id": 7000170}])
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        d = result.to_dict()
        assert "skill_analysis" in d
        assert "suggestions" in d
        assert "traits" in d
        assert "opp_traits" in d

    def test_to_dict_has_opp_traits(self, advisor):
        my = _make_pet(used_skills=[{"skill_id": 7000170}])
        opp = _make_pet(name="厉毒修萝", types=[7], buffs=[{"id": 20410080}])
        result = advisor.analyze(_battle_state(my, opp))
        d = result.to_dict()
        assert isinstance(d["opp_traits"], list)
        opp_names = [t["name"] for t in d["opp_traits"]]
        assert "侵蚀" in opp_names


class TestOppTraits:
    def test_opp_traits_populated(self, advisor):
        my = _make_pet(used_skills=[{"skill_id": 7000170}])
        opp = _make_pet(name="厉毒修萝", types=[7])
        result = advisor.analyze(_battle_state(my, opp))
        assert isinstance(result.opp_traits, list)
        names = [t["name"] for t in result.opp_traits]
        assert "侵蚀" in names

    def test_opp_traits_from_buffs(self, advisor):
        my = _make_pet(used_skills=[{"skill_id": 7000170}])
        opp = _make_pet(types=[0], buffs=[{"id": 20410080}])
        result = advisor.analyze(_battle_state(my, opp))
        names = [t["name"] for t in result.opp_traits]
        assert "临界防御" in names

    def test_opp_traits_empty_when_no_match(self, advisor):
        my = _make_pet(used_skills=[{"skill_id": 7000170}])
        opp = _make_pet(types=[0])
        result = advisor.analyze(_battle_state(my, opp))
        assert result.opp_traits == []
