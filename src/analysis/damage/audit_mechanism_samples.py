"""机制/runtime 对齐伤害审计样本提取。"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from src.analysis.damage.audit_ledger import (
    find_prediction,
    ledger_actual_damage,
    ledger_records_for_damage,
)
from src.analysis.damage.audit_mechanism import (
    decomposition_check,
    mechanism_strategy_totals,
)
from src.analysis.damage.audit_models import DamageMechanismSample
from src.analysis.damage.audit_runtime import (
    matched_runtime_value,
    runtime_skill_for_sample,
)
from src.analysis.damage.audit_utils import (
    first_present,
    optional_int,
    resolve_runtime_cost,
)
from src.analysis.replay_runner import ReplayResult


def iter_damage_mechanism_samples(
    result: ReplayResult,
    *,
    session: Optional[str] = None,
) -> Iterable[DamageMechanismSample]:
    """逐条对齐直接伤害、预测和技能运行时同步字段。"""
    latest_advice: Optional[Dict[str, Any]] = None
    for event in result.events:
        advice = event.battle_advice or latest_advice
        if event.battle_advice:
            latest_advice = event.battle_advice

        for formatted in event.formatted_events:
            if formatted.get("kind") != "damage":
                continue
            detail = formatted.get("detail", {})
            skill_name = detail.get("skill_name")
            if not skill_name:
                continue

            target_side = str(detail.get("target_side") or "")
            prediction = find_prediction(advice, str(skill_name), target_side)
            breakdown = (prediction or {}).get("damage_breakdown") or {}
            pred_obj = (prediction or {}).get("prediction") or {}
            predicted_total = pred_obj.get("total")
            if predicted_total is None and prediction:
                predicted_total = prediction.get("total_max_damage") or prediction.get("expected_damage")

            ledger_records = ledger_records_for_damage(event.state_after, detail)
            actual_total = (
                sum(ledger_actual_damage(item) for item in ledger_records)
                if ledger_records
                else int(detail.get("actual_damage") or detail.get("damage") or 0)
            )
            hit_count = int(detail.get("hit_count") or 1)
            if ledger_records:
                hit_count = max(hit_count, len(ledger_records))

            skill_id = (
                (prediction or {}).get("skill_id")
                or first_present(ledger_records, "skill_id")
            )
            target_pet_id = (
                first_present(ledger_records, "target_pet_id")
                or detail.get("target_pet_id")
            )
            runtime_skill, runtime_pet, runtime_source = runtime_skill_for_sample(
                event, target_side, skill_id, breakdown,
            )
            server_runtime = breakdown.get("server_runtime") or {}
            matched_target_key, matched_damage_param = matched_runtime_value(
                runtime_skill.get("damage_params_by_pet") or {},
                server_runtime,
                target_pet_id,
            )
            restraint_key, restraint_type = matched_runtime_value(
                runtime_skill.get("restraint_types_by_pet") or {},
                server_runtime,
                target_pet_id,
            )
            if matched_target_key is None:
                matched_target_key = restraint_key

            base_power = optional_int(breakdown.get("base_power") or (prediction or {}).get("power"))
            final_power = optional_int(breakdown.get("final_power") or breakdown.get("effective_power"))
            runtime_power = optional_int(breakdown.get("runtime_power"))
            strategy_totals = mechanism_strategy_totals(
                predicted_total,
                prediction or {},
                breakdown,
                matched_damage_param,
                restraint_type,
            )
            strategy_abs_errors = {
                name: abs(total - actual_total)
                for name, total in strategy_totals.items()
            }
            decomp_total, decomp_delta, decomp_matches = decomposition_check(
                runtime_skill,
                matched_damage_param,
            )

            yield DamageMechanismSample(
                session=session,
                round_num=event.round_num,
                event_index=event.index,
                skill_id=optional_int(skill_id),
                skill_name=str(skill_name),
                target_side=target_side,
                target_pet_id=optional_int(target_pet_id),
                actual_total=actual_total,
                predicted_total=optional_int(predicted_total),
                hit_count=hit_count,
                base_power=base_power,
                final_power=final_power,
                runtime_power=runtime_power,
                power_source=breakdown.get("power_source"),
                effectiveness_source=breakdown.get("effectiveness_source"),
                server_power_applied=bool(breakdown.get("server_power_applied")),
                server_power_multiplier=breakdown.get("server_power_multiplier"),
                server_power_skip_reason=breakdown.get("server_power_skip_reason"),
                matched_target_key=matched_target_key,
                matched_damage_param=optional_int(matched_damage_param),
                restraint_type=optional_int(restraint_type),
                runtime_state_source=runtime_source,
                runtime_pet_id=optional_int((runtime_pet or {}).get("pet_id")),
                runtime_pet_name=(runtime_pet or {}).get("name"),
                raw_damage=optional_int(runtime_skill.get("raw_damage")),
                rule_damage_param=optional_int(runtime_skill.get("rule_damage_param")),
                effect_damage_param=optional_int(runtime_skill.get("effect_damage_param")),
                buff_damage_param=optional_int(runtime_skill.get("buff_damage_param")),
                ex_damage_param=optional_int(runtime_skill.get("ex_damage_param")),
                damage_param_result=optional_int(runtime_skill.get("damage_param_result")),
                damage_type=optional_int(runtime_skill.get("damage_type")),
                cost_energy=resolve_runtime_cost(runtime_skill),
                set_cost_info=runtime_skill.get("set_cost_info"),
                skill_buff=runtime_skill.get("skill_buff"),
                enhance_info=runtime_skill.get("enhance_info"),
                cr_damage_params=runtime_skill.get("cr_damage_params"),
                extra_damage_type=runtime_skill.get("extra_damage_type"),
                strategy_totals=strategy_totals,
                strategy_abs_errors=strategy_abs_errors,
                decomposition_total=decomp_total,
                decomposition_delta=decomp_delta,
                decomposition_matches=decomp_matches,
            )
