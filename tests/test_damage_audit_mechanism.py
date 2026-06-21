"""机制伤害审计汇总测试。"""
from __future__ import annotations

from src.analysis.damage.audit_mechanism import (
    build_mechanism_report,
    build_multi_session_mechanism_report,
    candidate_totals,
    decomposition_check,
    field_presence,
    mechanism_strategy_totals,
)


def _sample(**overrides):
    data = {
        "session": "s1",
        "skill_id": 1,
        "skill_name": "追打",
        "actual_total": 100,
        "matched_damage_param": 150,
        "strategy_totals": {
            "production": 140,
            "damage_param_as_effective_power": 105,
        },
        "decomposition_delta": 0,
        "decomposition_matches": True,
        "raw_damage": 100,
        "rule_damage_param": 50,
        "set_cost_info": [{"type": 1}],
    }
    data.update(overrides)
    return data


def test_candidate_totals_preserves_existing_server_power_strategies():
    totals = candidate_totals(
        100,
        {"power": 80},
        {
            "base_power": 40,
            "final_power": 80,
            "runtime_power": 120,
            "server_runtime": {
                "power_source": "server_damage_params",
                "calc_effectiveness": 1.0,
                "display_effectiveness": 2.0,
            },
        },
    )

    assert totals["production"] == 100
    assert totals["static_power_fallback"] == 50
    assert totals["server_target_power_keep_restraint"] == 300
    assert totals["server_target_power_no_restraint"] == 150


def test_mechanism_strategy_totals_adds_damage_param_variants():
    totals = mechanism_strategy_totals(
        100,
        {"power": 80},
        {"final_power": 100, "base_power": 100},
        matched_damage_param=150,
        restraint_type=1,
    )

    assert totals["damage_param_as_effective_power"] == 150
    assert totals["damage_param_neutralized_by_restraint"] == 100


def test_decomposition_check_sums_runtime_damage_parts():
    assert decomposition_check({
        "raw_damage": 100,
        "rule_damage_param": 30,
        "effect_damage_param": 20,
    }, 150) == (150, 0, True)
    assert decomposition_check({}, 150) == (None, None, None)


def test_build_mechanism_report_groups_by_skill_and_recommends_better_strategy():
    samples = [
        _sample(),
        _sample(actual_total=100, strategy_totals={"production": 140, "damage_param_as_effective_power": 100}),
        _sample(actual_total=100, strategy_totals={"production": 140, "damage_param_as_effective_power": 100}),
    ]

    report = build_mechanism_report(samples)

    assert report["total_samples"] == 3
    assert report["matched_runtime_samples"] == 3
    assert report["strategy_compare"]["production"]["mae"] == 40
    assert report["by_skill"]["追打"]["total"] == 3
    assert report["recommendations"]["追打"]["status"] == "likely_effective_param"
    assert report["decomposition_checks"]["overall"]["match_rate"] == 1.0
    assert report["field_presence"]["overall"]["set_cost_info"]["count"] == 3


def test_build_multi_session_mechanism_report_adds_session_summary():
    missing_session = _sample()
    missing_session.pop("session")
    report = build_multi_session_mechanism_report({
        "s1": {"samples": [missing_session]},
        "s2": {"samples": [_sample(session="existing")]},
    })

    assert report["sessions"] == ["s1", "s2"]
    assert report["session_count"] == 2
    assert report["samples"][0]["session"] == "s1"
    assert report["samples"][1]["session"] == "existing"


def test_field_presence_counts_non_empty_values_only():
    presence = field_presence([
        {"raw_damage": 0, "skill_buff": []},
        {"raw_damage": None, "skill_buff": [{"id": 1}]},
    ])

    assert presence["raw_damage"]["count"] == 1
    assert presence["skill_buff"]["count"] == 1
