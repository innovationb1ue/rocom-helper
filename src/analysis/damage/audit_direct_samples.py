"""普通直接伤害审计样本提取。"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from src.analysis.damage.audit_ledger import (
    find_prediction,
    ledger_actual_damage,
    ledger_records_for_damage,
)
from src.analysis.damage.audit_mechanism import candidate_totals
from src.analysis.damage.audit_models import DamageAuditSample
from src.analysis.replay_runner import ReplayResult


def iter_damage_audit_samples(result: ReplayResult) -> Iterable[DamageAuditSample]:
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

            hit_count = int(detail.get("hit_count") or 1)
            ledger_records = ledger_records_for_damage(event.state_after, detail)
            if ledger_records:
                ledger_total = sum(ledger_actual_damage(item) for item in ledger_records)
                hit_count = max(hit_count, len(ledger_records))
                actual_total = ledger_total
                actual_per_hit = int(round(ledger_total / max(1, hit_count)))
                actual_source = "+".join(
                    sorted({str(item.get("source")) for item in ledger_records if item.get("source")})
                ) or "damage_ledger"
                confidences = {str(item.get("confidence") or "") for item in ledger_records}
                actual_confidence = "low" if "low" in confidences else ("medium" if "medium" in confidences else "high")
                ledger_ids = [str(item.get("ledger_id")) for item in ledger_records if item.get("ledger_id")]
            else:
                actual_per_hit = int(detail.get("actual_damage") or detail.get("damage") or 0)
                actual_total = actual_per_hit * hit_count
                actual_source = "formatted_event"
                actual_confidence = "medium"
                ledger_ids = []
            target_side = str(detail.get("target_side") or "")
            prediction = find_prediction(advice, skill_name, target_side)
            predicted_total = None
            predicted_per_hit = None
            skill_id = None
            confidence = None
            flags: List[str] = []
            hint = None
            if prediction:
                skill_id = prediction.get("skill_id")
                pred_obj = prediction.get("prediction") or {}
                predicted_total = pred_obj.get("total")
                predicted_per_hit = pred_obj.get("per_hit")
                if predicted_total is None:
                    predicted_total = prediction.get("total_max_damage") or prediction.get("expected_damage")
                if predicted_per_hit is None:
                    predicted_per_hit = prediction.get("expected_damage")
                confidence = pred_obj.get("confidence") or prediction.get("confidence")
                flags = list(pred_obj.get("accuracy_flags") or [])
                hint = prediction.get("validation_hint")
                breakdown = prediction.get("damage_breakdown") or {}
            else:
                breakdown = {}

            error = predicted_total - actual_total if predicted_total is not None else None
            abs_error = abs(error) if error is not None else None
            pct_error = abs_error / max(1, actual_total) if abs_error is not None else None
            candidates = candidate_totals(predicted_total, prediction or {}, breakdown)
            candidate_errors = {
                name: abs(total - actual_total)
                for name, total in candidates.items()
            }
            yield DamageAuditSample(
                round_num=event.round_num,
                event_index=event.index,
                skill_name=str(skill_name),
                skill_id=skill_id,
                target_side=target_side,
                actual_per_hit=actual_per_hit,
                actual_total=actual_total,
                predicted_per_hit=predicted_per_hit,
                predicted_total=predicted_total,
                hit_count=hit_count,
                error=error,
                abs_error=abs_error,
                pct_error=round(pct_error, 4) if pct_error is not None else None,
                confidence=confidence,
                accuracy_flags=flags,
                validation_hint=hint,
                power_source=breakdown.get("power_source"),
                energy_cost_source=breakdown.get("energy_cost_source"),
                effectiveness_source=breakdown.get("effectiveness_source"),
                candidate_totals=candidates,
                candidate_abs_errors=candidate_errors,
                ledger_ids=ledger_ids,
                actual_source=actual_source,
                actual_confidence=actual_confidence,
                buff_modifiers={
                    "attacker": breakdown.get("attacker_buff_modifiers") or {},
                    "defender": breakdown.get("defender_buff_modifiers") or {},
                    "attacker_derived": breakdown.get("attacker_derived_buff_modifiers") or {},
                    "power": breakdown.get("buff_power_modifiers") or {},
                    "hit_count": breakdown.get("buff_hit_count_modifiers") or {},
                },
                derived_buffs=list(breakdown.get("attacker_derived_buffs") or []),
                ability_level=breakdown.get("ability_level"),
                power_mult=breakdown.get("power_mult"),
                server_power_applied=bool(breakdown.get("server_power_applied")),
                server_power_multiplier=breakdown.get("server_power_multiplier"),
                server_power_skip_reason=breakdown.get("server_power_skip_reason"),
                reflect_buff_applied=bool(breakdown.get("reflect_buff_applied")),
                reflect_candidate_effects=list(breakdown.get("reflect_candidate_effects") or []),
                reflect_confirmed_effects=list(breakdown.get("reflect_confirmed_effects") or []),
            )
