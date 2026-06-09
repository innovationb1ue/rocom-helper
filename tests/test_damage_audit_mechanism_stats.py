"""机制审计统计口径测试。"""
from __future__ import annotations

from src.analysis.damage.audit_mechanism_stats import (
    decomposition_summary,
    field_presence,
    mechanism_strategy_summary,
)


def test_mechanism_strategy_summary_groups_errors_by_strategy():
    summary = mechanism_strategy_summary([
        {
            "actual_total": 100,
            "strategy_totals": {
                "production": 120,
                "damage_param_as_effective_power": 90,
            },
        },
        {
            "actual_total": 200,
            "strategy_totals": {
                "production": 150,
                "damage_param_as_effective_power": "bad",
            },
        },
        {"actual_total": None, "strategy_totals": {"production": 999}},
    ])

    assert summary["production"] == {"samples": 2, "mae": 35, "mape": 0.225}
    assert summary["damage_param_as_effective_power"] == {"samples": 1, "mae": 10, "mape": 0.1}


def test_decomposition_summary_reports_match_rate_and_delta_error():
    summary = decomposition_summary([
        {"decomposition_matches": True, "decomposition_delta": 0},
        {"decomposition_matches": False, "decomposition_delta": -4},
        {"decomposition_matches": None, "decomposition_delta": 100},
    ])

    assert summary == {
        "checked": 2,
        "matched": 1,
        "match_rate": 0.5,
        "mae_delta": 2,
    }


def test_decomposition_summary_handles_no_checked_samples():
    summary = decomposition_summary([
        {"decomposition_matches": None, "decomposition_delta": 4},
    ])

    assert summary == {
        "checked": 0,
        "matched": 0,
        "match_rate": None,
        "mae_delta": None,
    }


def test_field_presence_counts_values_with_audit_semantics():
    presence = field_presence([
        {"raw_damage": 0, "set_cost_info": [], "skill_buff": [{"id": 1}]},
        {"raw_damage": None, "set_cost_info": [{"type": 1}], "skill_buff": []},
    ])

    assert presence["raw_damage"] == {"count": 1, "rate": 0.5}
    assert presence["set_cost_info"] == {"count": 1, "rate": 0.5}
    assert presence["skill_buff"] == {"count": 1, "rate": 0.5}


def test_field_presence_handles_empty_samples():
    presence = field_presence([])

    assert presence["raw_damage"] == {"count": 0, "rate": None}
    assert presence["skill_buff"] == {"count": 0, "rate": None}
