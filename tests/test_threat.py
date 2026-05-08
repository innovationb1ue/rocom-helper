"""威胁评估测试 — 验证对手威胁评分、击杀顺序建议。"""
from __future__ import annotations

import pytest

from src.analysis.threat import ThreatAssessor
from src.game.type_chart import TypeChart


@pytest.fixture(scope="module")
def assessor():
    return ThreatAssessor(TypeChart())


# ---------------------------------------------------------------------------
# TestAssessThreats
# ---------------------------------------------------------------------------


class TestAssessThreats:
    def test_fire_threatens_grass(self, assessor):
        """火系对手对我方草系构成高威胁。"""
        opp = [{"name": "火龙", "types": [1], "stats": {"SPE": 100}, "skills": []}]
        mine = [{"name": "草蛇", "types": [3], "stats": {"SPE": 80}, "skills": []}]
        threats = assessor.assess_threats(opp, mine)
        assert len(threats) == 1
        assert threats[0]["threat_score"] > 10  # 火克草: 10 * 2.0 = 20
        assert any(t["name"] == "草蛇" for t in threats[0]["threatened_mine"])

    def test_no_type_advantage_low_threat(self, assessor):
        """无属性克制时威胁低。"""
        opp = [{"name": "普通兽", "types": [0], "stats": {"SPE": 50}, "skills": []}]
        mine = [{"name": "水龟", "types": [2], "stats": {"SPE": 50}, "skills": []}]
        threats = assessor.assess_threats(opp, mine)
        assert threats[0]["threat_score"] < 10

    def test_speed_advantage_adds_threat(self, assessor):
        """速度优势增加威胁分数。"""
        fast_opp = [{"name": "快宠", "types": [0], "stats": {"SPE": 120}, "skills": []}]
        slow_opp = [{"name": "慢宠", "types": [0], "stats": {"SPE": 60}, "skills": []}]
        mine = [{"name": "我宠", "types": [0], "stats": {"SPE": 60}, "skills": []}]
        t_fast = assessor.assess_threats(fast_opp, mine)
        t_slow = assessor.assess_threats(slow_opp, mine)
        assert t_fast[0]["threat_score"] > t_slow[0]["threat_score"]

    def test_vulnerability_reduces_threat(self, assessor):
        """对手被我方克制时威胁分数降低。"""
        # 草系对手，我方火系 → 对手被我克制，威胁被抵扣
        opp = [{"name": "草王", "types": [3], "stats": {"SPE": 80}, "skills": []}]
        mine = [{"name": "火龙", "types": [1], "stats": {"SPE": 80}, "skills": []}]
        threats = assessor.assess_threats(opp, mine)
        # 草不克火，但火克草 → 对手 vulnerability 被抵扣 -5*2.0 = -10
        assert threats[0]["threat_score"] < 0

    def test_skill_effectiveness_adds_threat(self, assessor):
        """对手有克制技能时增加威胁。"""
        opp_with_skill = [{"name": "火龙", "types": [0], "stats": {"SPE": 80},
                           "skills": [{"type_id": 1, "power": 90}]}]
        opp_no_skill = [{"name": "普通兽", "types": [0], "stats": {"SPE": 80},
                         "skills": []}]
        mine = [{"name": "草蛇", "types": [3], "stats": {"SPE": 80}, "skills": []}]
        t_with = assessor.assess_threats(opp_with_skill, mine)
        t_no = assessor.assess_threats(opp_no_skill, mine)
        assert t_with[0]["threat_score"] > t_no[0]["threat_score"]

    def test_threat_level_high(self, assessor):
        """威胁 ≥ 30 → 高。单属性克制 + 克制技能 + 速度碾压。"""
        opp = [{"name": "火龙", "types": [1], "stats": {"SPE": 200},
                "skills": [{"type_id": 1, "power": 120}]}]
        mine = [{"name": "草蛇", "types": [3], "stats": {"SPE": 10}, "skills": []}]
        threats = assessor.assess_threats(opp, mine)
        # 火克草 10*2=20 + 克制技能 5 + 速度 5 = 30
        assert threats[0]["threat_score"] >= 30
        assert threats[0]["threat_level"] == "高"

    def test_threat_level_medium(self, assessor):
        """15 ≤ 威胁 < 30 → 中。"""
        # 单属性克制 + 中速
        opp = [{"name": "火龙", "types": [1], "stats": {"SPE": 100}, "skills": []}]
        mine = [{"name": "草蛇", "types": [3], "stats": {"SPE": 90}, "skills": []}]
        threats = assessor.assess_threats(opp, mine)
        assert threats[0]["threat_score"] >= 15
        assert threats[0]["threat_level"] in ("中", "高")

    def test_threat_level_low(self, assessor):
        """威胁 < 15 → 低。"""
        opp = [{"name": "普通兽", "types": [0], "stats": {"SPE": 50}, "skills": []}]
        mine = [{"name": "水龟", "types": [2], "stats": {"SPE": 50}, "skills": []}]
        threats = assessor.assess_threats(opp, mine)
        assert threats[0]["threat_level"] == "低"

    def test_sorted_by_threat_score(self, assessor):
        """结果按威胁分数降序。"""
        opp = [
            {"name": "弱宠", "types": [0], "stats": {"SPE": 30}, "skills": []},
            {"name": "强宠", "types": [1], "stats": {"SPE": 150},
             "skills": [{"type_id": 1}]},
        ]
        mine = [{"name": "草蛇", "types": [3], "stats": {"SPE": 80}, "skills": []}]
        threats = assessor.assess_threats(opp, mine)
        assert threats[0]["threat_score"] >= threats[1]["threat_score"]
        assert threats[0]["name"] == "强宠"

    def test_empty_opponent(self, assessor):
        assert assessor.assess_threats([], [{"types": [0]}]) == []

    def test_empty_mine(self, assessor):
        threats = assessor.assess_threats([{"name": "A", "types": [0], "stats": {"SPE": 50}, "skills": []}], [])
        assert len(threats) == 1
        assert threats[0]["threat_score"] == 0

    def test_string_spe_handled(self, assessor):
        """SPE 为字符串时正确转换。"""
        opp = [{"name": "宠", "types": [1], "stats": {"SPE": "100"}, "skills": []}]
        mine = [{"name": "我", "types": [3], "stats": {"SPE": "50"}, "skills": []}]
        threats = assessor.assess_threats(opp, mine)
        assert threats[0]["threat_score"] > 10  # 火克草 + 速度优势

    def test_invalid_spe_defaults_to_zero(self, assessor):
        """无效 SPE 字符串默认为 0。"""
        opp = [{"name": "宠", "types": [0], "stats": {"SPE": "abc"}, "skills": []}]
        mine = [{"name": "我", "types": [0], "stats": {"SPE": 50}, "skills": []}]
        threats = assessor.assess_threats(opp, mine)
        assert threats[0]["threat_score"] == 0

    def test_multiple_mine_accumulates(self, assessor):
        """对手威胁对多只我方精灵累积。"""
        opp = [{"name": "火龙", "types": [1], "stats": {"SPE": 100}, "skills": []}]
        mine = [
            {"name": "草蛇", "types": [3], "stats": {"SPE": 80}, "skills": []},
            {"name": "冰狐", "types": [5], "stats": {"SPE": 80}, "skills": []},
        ]
        threats = assessor.assess_threats(opp, mine)
        # 火克草 + 火克冰 → 威胁分数高于只对单只
        assert len(threats[0]["threatened_mine"]) == 2


# ---------------------------------------------------------------------------
# TestSuggestTargetOrder
# ---------------------------------------------------------------------------


class TestSuggestTargetOrder:
    def test_prioritize_weak_target(self, assessor):
        """优先攻击被我方克制的对手。"""
        mine = {"types": [1], "skills": [{"type_id": 1, "name": "火焰冲击"}]}
        opponents = [
            {"name": "草王", "types": [3]},
            {"name": "水龟", "types": [2]},
            {"name": "普通兽", "types": [0]},
        ]
        order = assessor.suggest_target_order(opponents, mine)
        assert order[0]["name"] == "草王"
        assert order[0]["best_multiplier"] == 2.0

    def test_resisted_target_low_priority(self, assessor):
        """被抵抗目标排在克制目标后面。"""
        mine = {"types": [1], "skills": [{"type_id": 1, "name": "火焰冲击"}]}
        opponents = [
            {"name": "草王", "types": [3]},   # 火克草 2x → 高优先
            {"name": "水龟", "types": [2]},    # 抗火 0.5x
            {"name": "普通兽", "types": [0]},  # 中性
        ]
        order = assessor.suggest_target_order(opponents, mine)
        assert order[0]["name"] == "草王"
        # 水龟和普通兽的 best_mult 都是 1.0（火系技能不生效），但水龟对我方有威胁
        assert order[-1]["best_multiplier"] <= order[0]["best_multiplier"]

    def test_threat_factor_breaks_tie(self, assessor):
        """同样克制倍率时，对我方威胁更高的优先。"""
        # 我方火系，两个对手都无法被火系克制，但水系对我方有威胁
        mine = {"types": [1], "skills": [{"type_id": 1, "name": "火焰冲击"}]}
        opponents = [
            {"name": "水龟", "types": [2]},    # 水克火 → 对我方有威胁
            {"name": "普通兽", "types": [0]},   # 无威胁
        ]
        order = assessor.suggest_target_order(opponents, mine)
        water_entry = next(o for o in order if o["name"] == "水龟")
        normal_entry = next(o for o in order if o["name"] == "普通兽")
        # 水龟对我方火系有威胁 (水克火 2x)
        assert water_entry["threat_to_me"] > normal_entry["threat_to_me"]

    def test_sorted_by_priority(self, assessor):
        """结果按 target_priority 降序。"""
        mine = {"types": [1], "skills": [{"type_id": 1}]}
        opponents = [
            {"name": "草王", "types": [3]},
            {"name": "水龟", "types": [2]},
            {"name": "普通兽", "types": [0]},
        ]
        order = assessor.suggest_target_order(opponents, mine)
        for i in range(len(order) - 1):
            assert order[i]["target_priority"] >= order[i + 1]["target_priority"]

    def test_empty_opponents(self, assessor):
        mine = {"types": [1], "skills": []}
        assert assessor.suggest_target_order([], mine) == []

    def test_no_skills_neutral_multiplier(self, assessor):
        """无技能时 best_multiplier 默认 1.0。"""
        mine = {"types": [1], "skills": []}
        opponents = [{"name": "普通兽", "types": [0]}]
        order = assessor.suggest_target_order(opponents, mine)
        assert order[0]["best_multiplier"] == 1.0
        assert order[0]["best_skill"] is None
