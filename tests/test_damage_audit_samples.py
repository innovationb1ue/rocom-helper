"""伤害审计样本提取测试。"""
from __future__ import annotations

from src.analysis.damage import audit_samples
from src.analysis.damage.audit_ledger import (
    find_prediction,
    ledger_actual_damage,
    ledger_records_for_damage,
)
from src.analysis.damage.audit_models import DamageAuditSample, DamageMechanismSample
from src.analysis.damage.audit_direct_samples import iter_damage_audit_samples as iter_direct_damage_audit_samples
from src.analysis.damage.audit_mechanism_samples import (
    iter_damage_mechanism_samples as iter_direct_damage_mechanism_samples,
)
from src.analysis.damage.audit_runtime import (
    attacker_pet_candidates,
    matched_runtime_value,
    runtime_skill_for_sample,
)
from src.analysis.damage.audit_samples import (
    iter_damage_audit_samples,
    iter_damage_mechanism_samples,
)
from src.analysis.damage_audit import (
    _ledger_actual_damage,
    _ledger_records_for_damage,
)
from src.analysis.replay_runner import ReplayEventSnapshot, ReplayResult


def _event(**overrides):
    data = {
        "index": 1,
        "opcode": 0x1324,
        "kind": "action_resolve",
        "round_num": 1,
        "state_before": {"my_active": {"skill_runtime": {}}, "my_pets": [], "opp_pets": []},
        "state_after": {"field_context": {"damage_ledger": []}},
        "formatted_events": [],
        "battle_advice": None,
    }
    data.update(overrides)
    return ReplayEventSnapshot(**data)


def test_audit_samples_keeps_compatibility_reexports():
    assert audit_samples.DamageAuditSample is DamageAuditSample
    assert audit_samples.DamageMechanismSample is DamageMechanismSample
    assert audit_samples.ledger_records_for_damage is ledger_records_for_damage
    assert audit_samples.ledger_actual_damage is ledger_actual_damage
    assert audit_samples.find_prediction is find_prediction
    assert audit_samples.runtime_skill_for_sample is runtime_skill_for_sample
    assert audit_samples.matched_runtime_value is matched_runtime_value


def test_ledger_records_for_damage_prefers_explicit_ids_and_keeps_overkill_damage():
    ledger = [
        {"ledger_id": "a", "event_kind": "damage", "skill_name": "追打", "actual_damage": 112},
        {"ledger_id": "b", "event_kind": "damage", "skill_name": "追打", "actual_damage": 20},
    ]
    detail = {"ledger_ids": ["a"], "ledger_id": "a", "skill_name": "追打"}

    records = ledger_records_for_damage({"field_context": {"damage_ledger": ledger}}, detail)

    assert [record["ledger_id"] for record in records] == ["a"]
    assert ledger_actual_damage(records[0]) == 112
    assert _ledger_records_for_damage({"field_context": {"damage_ledger": ledger}}, detail) == records
    assert _ledger_actual_damage(records[0]) == 112


def test_ledger_records_for_damage_falls_back_to_latest_matching_damage_event():
    ledger = [
        {"ledger_id": "old", "event_kind": "damage", "skill_name": "追打", "hp_after": 10, "damage": 30},
        {"ledger_id": "new", "event_kind": "damage", "skill_name": "追打", "hp_after": 10, "damage": 40},
    ]

    records = ledger_records_for_damage(
        {"field_context": {"damage_ledger": ledger}},
        {"skill_name": "追打", "hp_after": 10},
    )

    assert [record["ledger_id"] for record in records] == ["new"]


def test_find_prediction_uses_target_side_to_pick_analysis_list():
    advice = {
        "skill_analysis": [{"skill_name": "我方技能", "skill_id": 1}],
        "opp_skill_analysis": [{"skill_name": "对手技能", "skill_id": 2}],
    }

    assert find_prediction(advice, "我方技能", "敌方")["skill_id"] == 1
    assert find_prediction(advice, "对手技能", "我方")["skill_id"] == 2
    assert find_prediction(None, "技能", "敌方") is None


def test_runtime_skill_for_sample_prefers_state_before_then_state_after_then_breakdown():
    state_before = {"my_active": {"pet_id": 1, "skill_runtime": {"1001": {"raw_damage": 10}}}, "my_pets": []}
    state_after = {"my_active": {"pet_id": 1, "skill_runtime": {"1001": {"raw_damage": 20}}}, "my_pets": []}
    event = _event(state_before=state_before, state_after=state_after)

    runtime, pet, source = runtime_skill_for_sample(event, "敌方", 1001, {})

    assert runtime["raw_damage"] == 10
    assert pet["pet_id"] == 1
    assert source == "state_before"

    fallback_event = _event(state_before={"my_active": {"skill_runtime": {}}, "my_pets": []}, state_after={})
    runtime, pet, source = runtime_skill_for_sample(
        fallback_event,
        "敌方",
        1001,
        {"runtime_skill": {"raw_damage": 30}},
    )
    assert runtime["raw_damage"] == 30
    assert pet is None
    assert source == "prediction_breakdown"


def test_attacker_pet_candidates_and_matched_runtime_value_keep_side_semantics():
    state = {
        "my_active": {"name": "我方当前"},
        "opp_active": {"name": "对手当前"},
        "my_pets": [{"name": "我方后备"}],
        "opp_pets": [{"name": "对手后备"}],
    }

    assert [pet["name"] for pet in attacker_pet_candidates(state, "敌方")] == ["我方当前", "我方后备"]
    assert [pet["name"] for pet in attacker_pet_candidates(state, "我方")] == ["对手当前", "对手后备"]
    assert matched_runtime_value({"401": 99}, {"matched_target_key": "401"}, None) == ("401", 99)
    assert matched_runtime_value({"real": 88}, {}, 20000000) == ("real", 88)


def test_iter_damage_audit_samples_extracts_prediction_and_ledger_fields():
    event = _event(
        state_after={
            "field_context": {
                "damage_ledger": [
                    {
                        "ledger_id": "l1",
                        "event_kind": "damage",
                        "skill_name": "追打",
                        "actual_damage": 120,
                        "source": "protocol",
                    }
                ]
            }
        },
        formatted_events=[{"kind": "damage", "detail": {"skill_name": "追打", "target_side": "敌方", "ledger_id": "l1"}}],
        battle_advice={
            "skill_analysis": [
                {
                    "skill_name": "追打",
                    "skill_id": 1001,
                    "prediction": {"total": 110, "per_hit": 110, "confidence": "high", "accuracy_flags": ["calibrated"]},
                    "validation_hint": "ok",
                    "damage_breakdown": {"power_source": "skill_config"},
                }
            ]
        },
    )

    samples = list(iter_damage_audit_samples(ReplayResult(total_packets=1, events=[event])))

    assert isinstance(samples[0], DamageAuditSample)
    assert samples[0].actual_total == 120
    assert samples[0].predicted_total == 110
    assert samples[0].actual_source == "protocol"
    assert samples[0].ledger_ids == ["l1"]


def test_direct_audit_samples_module_keeps_same_output_contract():
    event = _event(
        formatted_events=[
            {
                "kind": "damage",
                "detail": {
                    "skill_name": "追打",
                    "target_side": "敌方",
                    "actual_damage": 50,
                    "hit_count": 2,
                },
            }
        ],
        battle_advice={
            "skill_analysis": [
                {
                    "skill_name": "追打",
                    "skill_id": 1001,
                    "expected_damage": 60,
                    "damage_breakdown": {
                        "power_source": "skill_config",
                        "buff_power_modifiers": {"buff": 1.2},
                    },
                }
            ]
        },
    )

    samples = list(iter_direct_damage_audit_samples(ReplayResult(total_packets=1, events=[event])))

    assert isinstance(samples[0], DamageAuditSample)
    assert samples[0].actual_total == 100
    assert samples[0].predicted_total == 60
    assert samples[0].skill_id == 1001
    assert samples[0].power_source == "skill_config"
    assert samples[0].buff_modifiers["power"] == {"buff": 1.2}


def test_iter_damage_mechanism_samples_extracts_runtime_alignment():
    runtime = {
        "raw_damage": 90,
        "rule_damage_param": 10,
        "effect_damage_param": 0,
        "buff_damage_param": 5,
        "ex_damage_param": 0,
        "damage_params_by_pet": {"401": 105},
        "restraint_types_by_pet": {"401": 1},
        "cost_energy_result": 2,
    }
    event = _event(
        state_before={"my_active": {"pet_id": 1, "name": "我方", "skill_runtime": {"1001": runtime}}, "my_pets": []},
        state_after={
            "field_context": {
                "damage_ledger": [
                    {"ledger_id": "l1", "event_kind": "damage", "skill_name": "追打", "skill_id": 1001, "target_pet_id": 401, "actual_damage": 120}
                ]
            }
        },
        formatted_events=[{"kind": "damage", "detail": {"skill_name": "追打", "target_side": "敌方", "target_pet_id": 401, "ledger_id": "l1"}}],
        battle_advice={
            "skill_analysis": [
                {
                    "skill_name": "追打",
                    "skill_id": 1001,
                    "prediction": {"total": 110, "per_hit": 110},
                    "damage_breakdown": {"base_power": 100, "final_power": 110},
                }
            ]
        },
    )

    samples = list(iter_damage_mechanism_samples(ReplayResult(total_packets=1, events=[event]), session="s1"))

    assert isinstance(samples[0], DamageMechanismSample)
    assert samples[0].session == "s1"
    assert samples[0].runtime_state_source == "state_before"
    assert samples[0].matched_damage_param == 105
    assert samples[0].restraint_type == 1
    assert samples[0].decomposition_total == 105
    assert samples[0].cost_energy == 2


def test_mechanism_samples_module_keeps_same_output_contract():
    runtime = {
        "raw_damage": 90,
        "damage_params_by_pet": {"401": 105},
        "cost_energy_result": 2,
    }
    event = _event(
        state_before={"my_active": {"pet_id": 1, "name": "我方", "skill_runtime": {"1001": runtime}}, "my_pets": []},
        state_after={
            "field_context": {
                "damage_ledger": [
                    {"ledger_id": "l1", "event_kind": "damage", "skill_name": "追打", "skill_id": 1001, "target_pet_id": 401, "actual_damage": 120}
                ]
            }
        },
        formatted_events=[{"kind": "damage", "detail": {"skill_name": "追打", "target_side": "敌方", "target_pet_id": 401, "ledger_id": "l1"}}],
        battle_advice={
            "skill_analysis": [
                {
                    "skill_name": "追打",
                    "skill_id": 1001,
                    "prediction": {"total": 110},
                    "damage_breakdown": {"base_power": 100},
                }
            ]
        },
    )

    samples = list(
        iter_direct_damage_mechanism_samples(
            ReplayResult(total_packets=1, events=[event]),
            session="s2",
        )
    )

    assert isinstance(samples[0], DamageMechanismSample)
    assert samples[0].session == "s2"
    assert samples[0].actual_total == 120
    assert samples[0].predicted_total == 110
    assert samples[0].matched_damage_param == 105
    assert samples[0].runtime_state_source == "state_before"
