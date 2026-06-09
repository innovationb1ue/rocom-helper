"""普通伤害审计汇总测试。"""
from __future__ import annotations

from src.analysis.damage.audit_summary import (
    candidate_strategy_summary,
    group_samples,
    source_counts,
    summarize_damage_samples,
    summarize_multi_session_damage_audit,
)


def _sample(**overrides):
    data = {
        "skill_name": "火焰冲击",
        "skill_id": 1,
        "actual_total": 100,
        "predicted_total": 90,
        "abs_error": 10,
        "pct_error": 0.1,
        "confidence": "high",
        "power_source": "skill_config",
        "energy_cost_source": "skill_config",
        "effectiveness_source": "type_chart",
        "server_power_applied": False,
        "candidate_abs_errors": {"production": 10, "static_power_fallback": 30},
    }
    data.update(overrides)
    return data


def test_summarize_damage_samples_counts_accuracy_buckets_and_sources():
    report = summarize_damage_samples([
        _sample(),
        _sample(actual_total=100, predicted_total=160, abs_error=60, pct_error=0.6),
        _sample(predicted_total=None, abs_error=None, pct_error=None, confidence=None),
    ])

    assert report["total_direct_damage"] == 3
    assert report["matched_predictions"] == 2
    assert report["mae"] == 35
    assert report["mape"] == 0.35
    assert report["within_10pct"] == 1
    assert report["within_25pct"] == 1
    assert len(report["catastrophic_high_confidence"]) == 1
    assert report["source_counts"]["power_source"]["skill_config"] == 2
    assert report["candidate_strategies"]["production"]["mae"] == 10


def test_summarize_multi_session_damage_audit_keeps_session_and_skill_breakdowns():
    s1 = summarize_damage_samples([_sample(skill_name="火焰冲击")])
    s2 = summarize_damage_samples([_sample(skill_name="水波术")])

    aggregate = summarize_multi_session_damage_audit({"s1": s1, "s2": s2})

    assert aggregate["session_count"] == 2
    assert aggregate["total_direct_damage"] == 2
    assert aggregate["by_session"]["s1"]["matched_predictions"] == 1
    assert aggregate["by_skill"]["火焰冲击"]["sessions"] == ["s1"]
    assert aggregate["by_skill"]["水波术"]["sessions"] == ["s2"]


def test_group_samples_sorts_by_total_count():
    grouped = group_samples([
        _sample(skill_name="少"),
        _sample(skill_name="多"),
        _sample(skill_name="多"),
    ], "skill_name")

    assert list(grouped)[:2] == ["多", "少"]
    assert grouped["多"]["total"] == 2


def test_source_counts_and_candidate_strategy_summary_are_independent_helpers():
    samples = [_sample(), _sample(server_power_applied=True, candidate_abs_errors={"production": 20})]

    assert source_counts(samples)["server_power_applied"] == {"False": 1, "True": 1}
    assert candidate_strategy_summary(samples)["production"]["mae"] == 15
