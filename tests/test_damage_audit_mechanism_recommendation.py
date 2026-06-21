"""机制审计推荐策略测试。"""
from __future__ import annotations

from src.analysis.damage.audit_mechanism_recommendation import mechanism_recommendation


def _sample(skill_id=1):
    return {"skill_id": skill_id}


def _summary(**strategies):
    return {"strategy_compare": strategies}


def test_mechanism_recommendation_requires_three_samples():
    recommendation = mechanism_recommendation([_sample(), _sample()], _summary())

    assert recommendation["status"] == "insufficient_samples"
    assert recommendation["reason"] == "matched direct damage samples below 3"


def test_mechanism_recommendation_keeps_light_special_audit_only():
    recommendation = mechanism_recommendation(
        [_sample(7060130), _sample(), _sample()],
        _summary(
            production={"samples": 3, "mape": 0.5},
            damage_param_as_effective_power={"samples": 3, "mape": 0.1},
        ),
    )

    assert recommendation["status"] == "audit_only"
    assert "child effects settle after base damage" in recommendation["reason"]


def test_mechanism_recommendation_keeps_uncomparable_candidates_audit_only():
    recommendation = mechanism_recommendation(
        [_sample(), _sample(), _sample()],
        _summary(
            production={"samples": 3, "mape": 0.4},
            damage_param_as_effective_power={"samples": 2, "mape": 0.1},
        ),
    )

    assert recommendation == {
        "status": "audit_only",
        "reason": "damage-param candidates are not comparable yet",
    }


def test_mechanism_recommendation_detects_effective_power_improvement():
    recommendation = mechanism_recommendation(
        [_sample(), _sample(), _sample()],
        _summary(
            production={"samples": 3, "mape": 0.4},
            damage_param_as_effective_power={"samples": 3, "mape": 0.2},
        ),
    )

    assert recommendation["status"] == "likely_effective_param"
    assert recommendation["best_strategy"] == "damage_param_as_effective_power"
    assert "improves MAPE from 0.4 to 0.2" in recommendation["reason"]


def test_mechanism_recommendation_detects_restraint_whitelist_candidate():
    recommendation = mechanism_recommendation(
        [_sample(), _sample(), _sample()],
        _summary(
            production={"samples": 3, "mape": 0.4},
            damage_param_as_effective_power={"samples": 3, "mape": 0.35},
            damage_param_neutralized_by_restraint={"samples": 3, "mape": 0.1},
        ),
    )

    assert recommendation["status"] == "candidate_for_whitelist"
    assert recommendation["best_strategy"] == "damage_param_neutralized_by_restraint"


def test_mechanism_recommendation_keeps_minor_improvement_audit_only():
    recommendation = mechanism_recommendation(
        [_sample(), _sample(), _sample()],
        _summary(
            production={"samples": 3, "mape": 0.4},
            damage_param_as_effective_power={"samples": 3, "mape": 0.35},
        ),
    )

    assert recommendation == {
        "status": "audit_only",
        "reason": "damage-param candidates do not materially improve production",
    }
