"""BattleProcessor analysis helper tests."""
from __future__ import annotations

from dataclasses import dataclass

from src.analysis import processor_analysis
from src.analysis.constants import OPCODE_ACTION_RESOLVE, OPCODE_ROUND_START


@dataclass
class FakeAdvice:
    skill_analysis: list

    def to_dict(self):
        return {"skill_analysis": self.skill_analysis}


class FakeAdvisor:
    def __init__(self, *advices):
        self.advices = list(advices)
        self.states = []

    def analyze(self, state):
        self.states.append(state)
        if self.advices:
            return self.advices.pop(0)
        return FakeAdvice([])


@dataclass
class FakeRecommendation:
    actions: list
    payload: dict

    def to_dict(self):
        return dict(self.payload)


class FakeEngine:
    def __init__(self, recommendation):
        self.recommendation = recommendation
        self.states = []

    def recommend(self, state):
        self.states.append(state)
        return self.recommendation


def test_compute_damage_analysis_returns_none_without_skills():
    assert processor_analysis.compute_damage_analysis(
        {"round": 1},
        advisor=FakeAdvisor(FakeAdvice([])),
    ) is None


def test_compute_damage_analysis_serializes_advice():
    advice = processor_analysis.compute_damage_analysis(
        {"round": 1},
        advisor=FakeAdvisor(FakeAdvice([{"skill_name": "撞击"}])),
    )

    assert advice == {"skill_analysis": [{"skill_name": "撞击"}]}


def test_has_usable_damage_predictions_requires_attack_damage_value():
    assert processor_analysis.has_usable_damage_predictions(None) is False
    assert processor_analysis.has_usable_damage_predictions({"skill_analysis": []}) is False
    assert processor_analysis.has_usable_damage_predictions({
        "skill_analysis": [{"skill_damage_type": 1, "expected_damage": 10}]
    }) is False
    assert processor_analysis.has_usable_damage_predictions({
        "skill_analysis": [{"skill_damage_type": 2, "expected_damage": None}]
    }) is False
    assert processor_analysis.has_usable_damage_predictions({
        "skill_analysis": [{"skill_damage_type": 3, "expected_damage": 0}]
    }) is True


def test_action_resolve_damage_analysis_falls_back_when_projected_has_no_damage():
    advisor = FakeAdvisor(
        FakeAdvice([{"skill_damage_type": 2, "expected_damage": None}]),
        FakeAdvice([{"skill_damage_type": 2, "expected_damage": 42}]),
    )

    advice = processor_analysis.compute_damage_analysis_for_event(
        opcode=OPCODE_ACTION_RESOLVE,
        detail={"entries": []},
        state={"round": 2, "battle_id": 1},
        state_before={"round": 1, "battle_id": 1},
        advisor=advisor,
    )

    assert advice == {"skill_analysis": [{"skill_damage_type": 2, "expected_damage": 42}]}
    assert len(advisor.states) == 2
    assert advisor.states[0]["round"] == 1
    assert advisor.states[1]["round"] == 2


def test_non_action_damage_analysis_uses_current_state_once():
    advisor = FakeAdvisor(FakeAdvice([{"skill_damage_type": 2, "expected_damage": 12}]))

    advice = processor_analysis.compute_damage_analysis_for_event(
        opcode=OPCODE_ROUND_START,
        detail={},
        state={"round": 3},
        state_before={"round": 2},
        advisor=advisor,
    )

    assert advice == {"skill_analysis": [{"skill_damage_type": 2, "expected_damage": 12}]}
    assert advisor.states == [{"round": 3}]


def test_compute_tactical_returns_none_for_missing_or_empty_recommendation():
    assert processor_analysis.compute_tactical(
        {"round": 1},
        engine=FakeEngine(None),
    ) is None
    assert processor_analysis.compute_tactical(
        {"round": 1},
        engine=FakeEngine(FakeRecommendation([], {"actions": []})),
    ) is None


def test_compute_tactical_with_reliability_adds_contract_field():
    state = {
        "round": 1,
        "opp_active": {"used_skills": [{"skill_id": 1}], "equipped_skills": []},
    }
    tactical = processor_analysis.compute_tactical_with_reliability(
        state,
        engine=FakeEngine(FakeRecommendation([{"action": "skill"}], {"actions": [{"score": 1.0}]})),
        battle_advice={"opp_skill_source": "used"},
    )

    assert tactical["actions"] == [{"score": 1.0}]
    assert "reliability" in tactical
    assert tactical["reliability"]["coverage"]["opponent_skill_source"] == "used"


def test_compute_tactical_returns_none_after_battle_finished():
    assert processor_analysis.compute_tactical(
        {"round": 10, "result": "WIN_HP", "opp_pets": [{"current_hp": 0}]},
        engine=FakeEngine(FakeRecommendation([{"action": "skill"}], {"actions": [{"score": 1.0}]})),
    ) is None


def test_low_confidence_ko_is_downgraded_before_reaching_frontend():
    state = {
        "round": 2,
        "opp_active": {"used_skills": [], "equipped_skills": []},
    }
    tactical = processor_analysis.compute_tactical_with_reliability(
        state,
        engine=FakeEngine(FakeRecommendation(
            [{"action": "skill"}],
            {
                "actions": [
                    {
                        "action_type": "skill",
                        "skill_id": 1,
                        "skill_name": "水幕冲击",
                        "score": 0.8,
                        "can_ko": True,
                        "category": "finisher",
                        "confidence": "medium",
                        "damage_dealt": 584,
                        "expected_gain": "本回合有击杀线，成功后取得宠物数优势",
                        "reason": "本回合有击杀线",
                        "metrics": {"can_ko": True},
                    },
                ],
                "primary_plan": "首选 水幕冲击：本回合有击杀线，成功后取得宠物数优势",
            },
        )),
        battle_advice={
            "skill_analysis": [
                {
                    "skill_id": 1,
                    "skill_name": "水幕冲击",
                    "confidence": "low",
                    "prediction": {
                        "confidence": "low",
                        "accuracy_flags": ["runtime_target_unmatched", "uncalibrated_skill"],
                    },
                },
            ],
        },
    )

    action = tactical["actions"][0]
    assert action["can_ko"] is False
    assert action["category"] == "confirm"
    assert action["confidence"] == "low"
    assert "待确认候选" in action["expected_gain"]
    assert tactical["confidence"] == "low"
    assert tactical["model_confidence"] == "medium"
    assert "击杀线" not in tactical["primary_plan"]
