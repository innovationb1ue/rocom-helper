"""战术推荐引擎单元测试。"""
import pytest
from src.analysis.tactical_engine import (
    TacticalEngine,
    TacticalRecommendation,
    ActionScore,
    OpponentAction,
    ResolvedOutcome,
    _clamp01,
    W_KO,
    W_OPP_KO,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pet(
    name: str = "测试宠",
    hp: int = 300,
    max_hp: int = 300,
    energy: int = 8,
    types: list = None,
    speed: int = 100,
    equipped_skills: list = None,
    used_skills: list = None,
    pet_id: int = 1,
    base_id: int = 100,
    atk: int = 80,
    defense: int = 70,
) -> dict:
    if types is None:
        types = [1]  # 普通
    if equipped_skills is None:
        equipped_skills = [
            {"skill_id": 7020370, "skill_name": "撞击", "equipped_slot": 0,
             "skill_damage_type": 2, "skill_element": 1, "cost_energy": 1},
        ]
    return {
        "name": name,
        "pet_id": pet_id,
        "base_id": base_id,
        "current_hp": hp,
        "max_hp": max_hp,
        "hp_pct": hp / max_hp,
        "energy": energy,
        "types": types,
        "base_speed": speed,
        "effective_speed": speed,
        "stats": [
            {"name": "HP", "total": max_hp},
            {"name": "ATK", "total": atk},
            {"name": "DEF", "total": defense},
            {"name": "SPATK", "total": atk},
            {"name": "SPDEF", "total": defense},
            {"name": "SPEED", "total": speed},
        ],
        "buffs": [],
        "equipped_skills": equipped_skills,
        "used_skills": used_skills or [],
        "level": 50,
    }


def _make_state(my_active=None, opp_active=None, my_pets=None, opp_pets=None, round_num=1):
    if my_active is None:
        my_active = _make_pet("我方宠", pet_id=1)
    if opp_active is None:
        opp_active = _make_pet("敌方宠", pet_id=101)
    if my_pets is None:
        my_pets = [my_active]
    if opp_pets is None:
        opp_pets = [opp_active]
    return {
        "battle_id": 1,
        "round": round_num,
        "phase": "selecting",
        "my_active": my_active,
        "opp_active": opp_active,
        "my_pets": my_pets,
        "opp_pets": opp_pets,
        "weather": None,
        "result": None,
    }


# ---------------------------------------------------------------------------
# Tests: _clamp01
# ---------------------------------------------------------------------------

class TestClamp:
    def test_normal(self):
        assert _clamp01(0.5) == 0.5

    def test_negative(self):
        assert _clamp01(-1.0) == 0.0

    def test_over_one(self):
        assert _clamp01(2.0) == 1.0


# ---------------------------------------------------------------------------
# Tests: Action enumeration
# ---------------------------------------------------------------------------

class TestActionEnumeration:
    def test_skills_and_switches(self):
        pet = _make_pet(
            equipped_skills=[
                {"skill_id": 7020370, "skill_name": "撞击", "equipped_slot": 0,
                 "skill_damage_type": 2, "skill_element": 1, "cost_energy": 1},
                {"skill_id": 7020370, "skill_name": "撞击2", "equipped_slot": 1,
                 "skill_damage_type": 2, "skill_element": 1, "cost_energy": 3},
            ],
            energy=10,
            pet_id=1,
        )
        other = _make_pet(name="替补宠", pet_id=2)
        engine = TacticalEngine()
        actions = engine._enumerate_our_actions(pet, [pet, other])
        skill_actions = [a for a in actions if a["action_type"] == "skill"]
        switch_actions = [a for a in actions if a["action_type"] == "switch"]
        assert len(skill_actions) == 2
        assert len(switch_actions) == 1
        assert switch_actions[0]["switch_to_name"] == "替补宠"

    def test_energy_gate_filters_skills(self):
        pet = _make_pet(
            equipped_skills=[
                {"skill_id": 7020370, "skill_name": "低耗", "equipped_slot": 0,
                 "skill_damage_type": 2, "skill_element": 1, "cost_energy": 1},
                {"skill_id": 7020371, "skill_name": "高耗", "equipped_slot": 1,
                 "skill_damage_type": 2, "skill_element": 1, "cost_energy": 8},
            ],
            energy=3,
        )
        engine = TacticalEngine()
        actions = engine._enumerate_our_actions(pet, [pet])
        skill_actions = [a for a in actions if a["action_type"] == "skill"]
        assert len(skill_actions) == 1
        assert skill_actions[0]["skill_name"] == "低耗"

    def test_dead_pets_excluded_from_switch(self):
        pet = _make_pet(pet_id=1)
        dead = _make_pet(name="死亡宠", hp=0, pet_id=2)
        alive = _make_pet(name="存活宠", pet_id=3)
        engine = TacticalEngine()
        actions = engine._enumerate_our_actions(pet, [pet, dead, alive])
        switches = [a for a in actions if a["action_type"] == "switch"]
        assert len(switches) == 1
        assert switches[0]["switch_to_name"] == "存活宠"


# ---------------------------------------------------------------------------
# Tests: Opponent prediction
# ---------------------------------------------------------------------------

class TestOpponentPrediction:
    def test_basic_skill_probabilities(self):
        opp = _make_pet(
            "敌方",
            energy=10,
            pet_id=101,
            equipped_skills=[
                {"skill_id": 7020370, "skill_name": "技能A", "skill_damage_type": 2,
                 "skill_element": 1, "cost_energy": 1},
            ],
        )
        engine = TacticalEngine()
        state = _make_state(opp_active=opp, opp_pets=[opp])
        predicted = engine._predict_opp_actions(opp, [opp], state)
        skills = [p for p in predicted if p.action_type == "skill"]
        assert len(skills) >= 1
        total = sum(p.probability for p in predicted)
        assert abs(total - 1.0) < 0.01

    def test_energy_filtering(self):
        opp = _make_pet(
            "敌方",
            energy=0,
            pet_id=101,
            equipped_skills=[
                {"skill_id": 7020370, "skill_name": "技能A", "skill_damage_type": 2,
                 "skill_element": 1, "cost_energy": 1},
            ],
        )
        engine = TacticalEngine()
        state = _make_state(opp_active=opp, opp_pets=[opp])
        predicted = engine._predict_opp_actions(opp, [opp], state)
        skills = [p for p in predicted if p.action_type == "skill"]
        assert len(skills) == 0

    def test_switch_probability_increases_with_low_hp(self):
        opp = _make_pet("敌方", hp=50, max_hp=300, pet_id=101)
        engine = TacticalEngine()
        state = _make_state(opp_active=opp, opp_pets=[opp])
        prob_low = engine._estimate_switch_probability(opp, state)

        opp_full = _make_pet("敌方", hp=300, max_hp=300, pet_id=101)
        prob_full = engine._estimate_switch_probability(opp_full, state)
        assert prob_low >= prob_full


# ---------------------------------------------------------------------------
# Tests: Outcome resolution
# ---------------------------------------------------------------------------

class TestOutcomeResolution:
    def test_faster_pet_kills_first(self):
        my = _make_pet("我方", speed=200, hp=300, pet_id=1)
        opp = _make_pet("敌方", speed=100, hp=10, pet_id=101)
        engine = TacticalEngine()

        our_action = {
            "action_type": "skill",
            "skill_id": 7020370,
            "skill_name": "撞击",
            "energy_cost": 1,
            "damage_type": 2,
            "skill_element": 1,
            "meta": {"damage_type": 2, "dam_para": [65], "energy_cost": [1],
                     "type": 1, "hit_para": 10000, "skill_dam_type": 2},
            "is_damage_skill": True,
        }
        opp_act = OpponentAction(action_type="switch", probability=1.0)

        outcome = engine._resolve_opp_switch_outcome(
            our_action, opp_act, my, opp, [opp], _make_state(), None,
        )
        assert outcome.we_ko is True
        assert outcome.opp_kos_us is False

    def test_switch_takes_damage(self):
        my = _make_pet("我方", speed=200, pet_id=1)
        opp = _make_pet("敌方", speed=100, pet_id=101)
        incoming = _make_pet("替补", hp=200, max_hp=300, pet_id=2)
        engine = TacticalEngine()

        our_action = {
            "action_type": "switch",
            "switch_to_name": "替补",
            "switch_to_pet": incoming,
            "energy_cost": 0,
        }
        opp_act = OpponentAction(action_type="skill", skill_id=7020370, probability=1.0)

        outcome = engine._resolve_switch_outcome(
            our_action, opp_act, my, opp, _make_state(), None,
        )
        assert outcome.our_damage_dealt == 0
        assert outcome.opp_damage_dealt > 0
        assert outcome.opp_kos_us is False  # HP 200 should survive


# ---------------------------------------------------------------------------
# Tests: Evaluation function
# ---------------------------------------------------------------------------

class TestEvaluation:
    def test_ko_scores_high(self):
        outcome_ko = ResolvedOutcome(
            our_damage_dealt=300, opp_damage_dealt=0,
            we_ko=True, opp_kos_us=False, we_act_first=True,
            our_remaining_hp=300, opp_remaining_hp=0,
            type_matchup_after=1.0, energy_after=7, pet_count_delta=1,
        )
        outcome_no_ko = ResolvedOutcome(
            our_damage_dealt=100, opp_damage_dealt=0,
            we_ko=False, opp_kos_us=False, we_act_first=True,
            our_remaining_hp=300, opp_remaining_hp=200,
            type_matchup_after=1.0, energy_after=7, pet_count_delta=0,
        )
        my = _make_pet()
        opp = _make_pet()
        engine = TacticalEngine()
        score_ko = engine._evaluate_outcome(outcome_ko, my, opp)
        score_no = engine._evaluate_outcome(outcome_no_ko, my, opp)
        assert score_ko > score_no

    def test_being_koed_scores_very_low(self):
        outcome_dead = ResolvedOutcome(
            our_damage_dealt=0, opp_damage_dealt=300,
            we_ko=False, opp_kos_us=True, we_act_first=False,
            our_remaining_hp=0, opp_remaining_hp=300,
            type_matchup_after=1.0, energy_after=8, pet_count_delta=-1,
        )
        my = _make_pet()
        opp = _make_pet()
        engine = TacticalEngine()
        score = engine._evaluate_outcome(outcome_dead, my, opp)
        assert score < 0


# ---------------------------------------------------------------------------
# Tests: Full recommendation
# ---------------------------------------------------------------------------

class TestRecommendation:
    def test_basic_recommendation(self):
        state = _make_state()
        engine = TacticalEngine()
        rec = engine.recommend(state)
        assert rec is not None
        assert len(rec.actions) >= 1
        assert all(a.score >= 0 for a in rec.actions if a.action_type == "skill")
        # Actions should be sorted by score descending
        scores = [a.score for a in rec.actions]
        assert scores == sorted(scores, reverse=True)

    def test_empty_state_returns_none(self):
        state = {"my_active": None, "opp_active": None}
        engine = TacticalEngine()
        assert engine.recommend(state) is None

    def test_to_dict_structure(self):
        state = _make_state()
        engine = TacticalEngine()
        rec = engine.recommend(state)
        d = rec.to_dict()
        assert "actions" in d
        assert "opp_predicted" in d
        assert "round_number" in d
        assert "confidence" in d
        assert isinstance(d["actions"], list)
        if d["actions"]:
            action = d["actions"][0]
            assert "score" in action
            assert "reason" in action
            assert "action_type" in action

    def test_with_multiple_switch_options(self):
        my = _make_pet("我方", pet_id=1, energy=10)
        alt1 = _make_pet("替补A", pet_id=2, hp=250, max_hp=300, types=[2])
        alt2 = _make_pet("替补B", pet_id=3, hp=280, max_hp=300, types=[3])
        opp = _make_pet("敌方", pet_id=101, types=[1])
        state = _make_state(my_active=my, opp_active=opp, my_pets=[my, alt1, alt2])
        engine = TacticalEngine()
        rec = engine.recommend(state)
        switches = [a for a in rec.actions if a.action_type == "switch"]
        assert len(switches) == 2

    def test_replay_session_runs(self):
        """集成测试：用真实回放数据验证引擎不崩溃。"""
        from pathlib import Path
        from tests.packet_reader import load_battle_packets
        from src.analysis.replay_runner import BattleReplayRunner

        packets = load_battle_packets(Path("tests/fixtures/packets/battle_session_1"))
        runner = BattleReplayRunner(include_analysis=False, include_hooks=False)
        result = runner.run(packets)

        engine = TacticalEngine()
        state = result.final_state
        if state.get("my_active") and state.get("opp_active"):
            rec = engine.recommend(state)
            assert rec is not None
            assert len(rec.actions) > 0
