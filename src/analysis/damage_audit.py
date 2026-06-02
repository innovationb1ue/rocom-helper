"""回放伤害预测对账。

只统计带技能名的直接技能伤害；中毒、天气、回合末等无技能名伤害不进入准确率指标。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.analysis.replay_runner import ReplayResult


@dataclass
class DamageAuditSample:
    round_num: int
    event_index: int
    skill_name: str
    skill_id: Optional[int]
    target_side: str
    actual_per_hit: int
    actual_total: int
    predicted_per_hit: Optional[int]
    predicted_total: Optional[int]
    hit_count: int
    error: Optional[int]
    abs_error: Optional[int]
    pct_error: Optional[float]
    confidence: Optional[str]
    accuracy_flags: List[str]
    validation_hint: Optional[str]
    power_source: Optional[str]
    energy_cost_source: Optional[str]
    effectiveness_source: Optional[str]
    candidate_totals: Dict[str, int]
    candidate_abs_errors: Dict[str, int]
    ledger_ids: List[str]
    actual_source: str
    actual_confidence: str
    buff_modifiers: Dict[str, Dict[str, float]]
    derived_buffs: List[Dict[str, Any]]
    ability_level: Optional[float]
    power_mult: Optional[float]
    server_power_applied: bool
    server_power_multiplier: Optional[float]
    server_power_skip_reason: Optional[str]
    reflect_buff_applied: bool
    reflect_candidate_effects: List[Dict[str, Any]]
    reflect_confirmed_effects: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DamageMechanismSample:
    session: Optional[str]
    round_num: int
    event_index: int
    skill_id: Optional[int]
    skill_name: str
    target_side: str
    target_pet_id: Optional[int]
    actual_total: int
    predicted_total: Optional[int]
    hit_count: int
    base_power: Optional[int]
    final_power: Optional[int]
    runtime_power: Optional[int]
    power_source: Optional[str]
    effectiveness_source: Optional[str]
    server_power_applied: bool
    server_power_multiplier: Optional[float]
    server_power_skip_reason: Optional[str]
    matched_target_key: Optional[str]
    matched_damage_param: Optional[int]
    restraint_type: Optional[int]
    runtime_state_source: str
    runtime_pet_id: Optional[int]
    runtime_pet_name: Optional[str]
    raw_damage: Optional[int]
    rule_damage_param: Optional[int]
    effect_damage_param: Optional[int]
    buff_damage_param: Optional[int]
    ex_damage_param: Optional[int]
    damage_param_result: Optional[int]
    damage_type: Optional[int]
    cost_energy: Optional[int]
    set_cost_info: Any
    skill_buff: Any
    enhance_info: Any
    cr_damage_params: Any
    extra_damage_type: Any
    strategy_totals: Dict[str, int]
    strategy_abs_errors: Dict[str, int]
    decomposition_total: Optional[int]
    decomposition_delta: Optional[int]
    decomposition_matches: Optional[bool]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_damage_audit(result: ReplayResult) -> Dict[str, Any]:
    samples = list(iter_damage_audit_samples(result))
    matched = [s for s in samples if s.predicted_total is not None]
    abs_errors = [s.abs_error for s in matched if s.abs_error is not None]
    pct_errors = [s.pct_error for s in matched if s.pct_error is not None]
    high_conf = [s for s in matched if s.confidence == "high"]
    catastrophic_high = [
        s.to_dict()
        for s in high_conf
        if s.pct_error is not None and s.pct_error > 0.5
    ]
    return {
        "total_direct_damage": len(samples),
        "matched_predictions": len(matched),
        "mae": round(mean(abs_errors), 2) if abs_errors else None,
        "mape": round(mean(pct_errors), 4) if pct_errors else None,
        "within_10pct": sum(1 for s in matched if s.pct_error is not None and s.pct_error <= 0.10),
        "within_25pct": sum(1 for s in matched if s.pct_error is not None and s.pct_error <= 0.25),
        "high_confidence_samples": len(high_conf),
        "source_counts": _source_counts([s.to_dict() for s in matched]),
        "candidate_strategies": _candidate_strategy_summary([s.to_dict() for s in matched]),
        "catastrophic_high_confidence": catastrophic_high,
        "samples": [s.to_dict() for s in samples],
    }


def build_damage_mechanism_report(
    result: ReplayResult,
    *,
    session: Optional[str] = None,
) -> Dict[str, Any]:
    """生成技能运行时伤害参数机制审计报告。"""
    samples = [s.to_dict() for s in iter_damage_mechanism_samples(result, session=session)]
    by_skill = _mechanism_group_by_skill(samples)
    strategy_compare = _mechanism_strategy_summary(samples)
    return {
        "total_samples": len(samples),
        "matched_runtime_samples": sum(1 for s in samples if s.get("matched_damage_param") is not None),
        "samples": samples,
        "by_skill": by_skill,
        "strategy_compare": strategy_compare,
        "damage_param_strategy_compare": strategy_compare,
        "decomposition_checks": {
            "overall": _decomposition_summary(samples),
            "by_skill": {
                name: item.get("decomposition_checks", {})
                for name, item in by_skill.items()
            },
        },
        "field_presence": {
            "overall": _field_presence(samples),
            "by_skill": {
                name: item.get("field_presence", {})
                for name, item in by_skill.items()
            },
        },
        "recommendations": {
            name: item.get("recommendation", {})
            for name, item in by_skill.items()
        },
    }


def build_multi_session_damage_mechanism_report(
    reports: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """聚合多场机制审计报告。"""
    samples: List[Dict[str, Any]] = []
    for session, report in reports.items():
        for sample in report.get("samples", []) or []:
            item = dict(sample)
            item.setdefault("session", session)
            samples.append(item)
    by_skill = _mechanism_group_by_skill(samples)
    strategy_compare = _mechanism_strategy_summary(samples)
    return {
        "sessions": list(reports.keys()),
        "session_count": len(reports),
        "total_samples": len(samples),
        "matched_runtime_samples": sum(1 for s in samples if s.get("matched_damage_param") is not None),
        "samples": samples,
        "by_skill": by_skill,
        "strategy_compare": strategy_compare,
        "damage_param_strategy_compare": strategy_compare,
        "decomposition_checks": {
            "overall": _decomposition_summary(samples),
            "by_skill": {
                name: item.get("decomposition_checks", {})
                for name, item in by_skill.items()
            },
        },
        "field_presence": {
            "overall": _field_presence(samples),
            "by_skill": {
                name: item.get("field_presence", {})
                for name, item in by_skill.items()
            },
        },
        "recommendations": {
            name: item.get("recommendation", {})
            for name, item in by_skill.items()
        },
    }


def build_multi_session_damage_audit(reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate several damage-audit reports without losing per-session detail."""
    all_samples: List[Dict[str, Any]] = []
    for session, report in reports.items():
        for sample in report.get("samples", []):
            all_samples.append({"session": session, **sample})

    matched = [s for s in all_samples if s.get("predicted_total") is not None]
    abs_errors = [s["abs_error"] for s in matched if s.get("abs_error") is not None]
    pct_errors = [s["pct_error"] for s in matched if s.get("pct_error") is not None]

    return {
        "sessions": list(reports.keys()),
        "session_count": len(reports),
        "total_direct_damage": len(all_samples),
        "matched_predictions": len(matched),
        "mae": round(mean(abs_errors), 2) if abs_errors else None,
        "mape": round(mean(pct_errors), 4) if pct_errors else None,
        "within_10pct": sum(1 for s in matched if s.get("pct_error") is not None and s["pct_error"] <= 0.10),
        "within_25pct": sum(1 for s in matched if s.get("pct_error") is not None and s["pct_error"] <= 0.25),
        "source_counts": _source_counts(matched),
        "candidate_strategies": _candidate_strategy_summary(matched),
        "by_skill": _group_samples(all_samples, "skill_name"),
        "by_session": {
            session: {
                "total_direct_damage": report.get("total_direct_damage", 0),
                "matched_predictions": report.get("matched_predictions", 0),
                "mae": report.get("mae"),
                "mape": report.get("mape"),
                "within_10pct": report.get("within_10pct", 0),
                "within_25pct": report.get("within_25pct", 0),
            }
            for session, report in reports.items()
        },
        "missing_prediction_samples": [
            s for s in all_samples
            if s.get("predicted_total") is None
        ][:20],
        "catastrophic_high_confidence": [
            s for s in matched
            if s.get("confidence") == "high"
            and s.get("pct_error") is not None
            and s["pct_error"] > 0.5
        ],
        "samples": all_samples,
    }


def build_damage_calibration(
    report: Dict[str, Any],
    *,
    min_samples: int = 3,
) -> Dict[str, Any]:
    """从审计报告生成只读校准配置草案。"""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for sample in report.get("samples", []) or []:
        skill_id = sample.get("skill_id")
        predicted = sample.get("predicted_total")
        actual = sample.get("actual_total")
        if skill_id is None or predicted in (None, 0) or actual is None:
            continue
        grouped.setdefault(str(skill_id), []).append(sample)

    skills: Dict[str, Dict[str, Any]] = {}
    skipped: Dict[str, str] = {}
    for skill_id, samples in grouped.items():
        if len(samples) < min_samples:
            skipped[skill_id] = "sample_count_below_min"
            continue
        before_errors = [
            abs(int(s["predicted_total"]) - int(s["actual_total"])) / max(1, int(s["actual_total"]))
            for s in samples
        ]
        pred_sum = sum(int(s["predicted_total"]) for s in samples)
        actual_sum = sum(int(s["actual_total"]) for s in samples)
        if pred_sum <= 0:
            skipped[skill_id] = "missing_predicted_total"
            continue
        multiplier = actual_sum / pred_sum
        adjusted = [max(1, round(int(s["predicted_total"]) * multiplier)) for s in samples]
        abs_errors = [
            abs(adj - int(sample["actual_total"]))
            for adj, sample in zip(adjusted, samples)
        ]
        after_errors = [
            err / max(1, int(sample["actual_total"]))
            for err, sample in zip(abs_errors, samples)
        ]
        before_mape = mean(before_errors) if before_errors else None
        after_mape = mean(after_errors) if after_errors else None
        if before_mape is not None and after_mape is not None and after_mape >= before_mape:
            skipped[skill_id] = "mape_not_improved"
            continue
        sessions = sorted({str(s.get("session")) for s in samples if s.get("session")})
        skills[skill_id] = {
            "multiplier": round(multiplier, 6),
            "sample_count": len(samples),
            "mae": round(mean(abs_errors), 2) if abs_errors else None,
            "mape": round(after_mape, 4) if after_mape is not None else None,
            "source_sessions": sessions,
            "notes": (
                "auto suggested from damage ledger; "
                f"baseline_mape={round(before_mape, 4) if before_mape is not None else None}"
            ),
        }

    return {
        "version": 1,
        "skills": dict(sorted(skills.items())),
        "meta": {
            "min_samples": min_samples,
            "source": "scripts.audit_damage_predictions",
            "skipped": skipped,
        },
    }


def build_special_damage_rules(report: Dict[str, Any]) -> Dict[str, Any]:
    """从协议账本生成特殊固定伤害规则草案。

    折射（7060130）已确认是光系魔伤，派生效果在本体伤害后结算，
    不能从其低伤害样本反推固定伤害规则。
    """
    return {
        "version": 1,
        "skills": {},
        "meta": {
            "source": "scripts.audit_damage_predictions",
            "special_skill_ids": [],
            "excluded_skill_ids": [7060130],
            "excluded_reasons": {
                "7060130": "confirmed light special damage; reflect child effects settle after base damage"
            },
        },
    }


def _source_counts(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    return {
        "power_source": dict(Counter(str(s.get("power_source") or "") for s in samples)),
        "energy_cost_source": dict(Counter(str(s.get("energy_cost_source") or "") for s in samples)),
        "effectiveness_source": dict(Counter(str(s.get("effectiveness_source") or "") for s in samples)),
        "server_power_applied": dict(Counter(str(bool(s.get("server_power_applied"))) for s in samples)),
    }


def _candidate_strategy_summary(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[int]] = {}
    grouped_pct: Dict[str, List[float]] = {}
    for sample in samples:
        actual = int(sample.get("actual_total") or 0)
        for name, abs_error in (sample.get("candidate_abs_errors") or {}).items():
            grouped.setdefault(name, []).append(abs_error)
            grouped_pct.setdefault(name, []).append(abs_error / max(1, actual))
    return {
        name: {
            "samples": len(errors),
            "mae": round(mean(errors), 2) if errors else None,
            "mape": round(mean(grouped_pct.get(name, [])), 4) if grouped_pct.get(name) else None,
        }
        for name, errors in sorted(grouped.items())
    }


def _group_samples(samples: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for sample in samples:
        name = str(sample.get(key) or "?")
        grouped.setdefault(name, []).append(sample)

    out: Dict[str, Dict[str, Any]] = {}
    for name, items in grouped.items():
        matched = [s for s in items if s.get("predicted_total") is not None]
        abs_errors = [s["abs_error"] for s in matched if s.get("abs_error") is not None]
        pct_errors = [s["pct_error"] for s in matched if s.get("pct_error") is not None]
        out[name] = {
            "total": len(items),
            "matched": len(matched),
            "mae": round(mean(abs_errors), 2) if abs_errors else None,
            "mape": round(mean(pct_errors), 4) if pct_errors else None,
            "within_25pct": sum(1 for s in matched if s.get("pct_error") is not None and s["pct_error"] <= 0.25),
            "sessions": sorted({str(s.get("session")) for s in items if s.get("session")}),
        }
    return dict(sorted(out.items(), key=lambda item: item[1]["total"], reverse=True))


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
            ledger_records = _ledger_records_for_damage(event.state_after, detail)
            if ledger_records:
                ledger_total = sum(_ledger_actual_damage(item) for item in ledger_records)
                hit_count = max(hit_count, len(ledger_records))
                actual_total = ledger_total
                actual_per_hit = int(round(ledger_total / max(1, hit_count)))
                actual_source = "+".join(sorted({str(item.get("source")) for item in ledger_records if item.get("source")})) or "damage_ledger"
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
            prediction = _find_prediction(advice, skill_name, target_side)
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
            candidates = _candidate_totals(predicted_total, prediction or {}, breakdown)
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
            prediction = _find_prediction(advice, str(skill_name), target_side)
            breakdown = (prediction or {}).get("damage_breakdown") or {}
            pred_obj = (prediction or {}).get("prediction") or {}
            predicted_total = pred_obj.get("total")
            if predicted_total is None and prediction:
                predicted_total = prediction.get("total_max_damage") or prediction.get("expected_damage")

            ledger_records = _ledger_records_for_damage(event.state_after, detail)
            actual_total = (
                sum(_ledger_actual_damage(item) for item in ledger_records)
                if ledger_records
                else int(detail.get("actual_damage") or detail.get("damage") or 0)
            )
            hit_count = int(detail.get("hit_count") or 1)
            if ledger_records:
                hit_count = max(hit_count, len(ledger_records))

            skill_id = (
                (prediction or {}).get("skill_id")
                or _first_present(ledger_records, "skill_id")
            )
            target_pet_id = (
                _first_present(ledger_records, "target_pet_id")
                or detail.get("target_pet_id")
            )
            runtime_skill, runtime_pet, runtime_source = _runtime_skill_for_sample(
                event, target_side, skill_id, breakdown,
            )
            server_runtime = breakdown.get("server_runtime") or {}
            matched_target_key, matched_damage_param = _matched_runtime_value(
                runtime_skill.get("damage_params_by_pet") or {},
                server_runtime,
                target_pet_id,
            )
            restraint_key, restraint_type = _matched_runtime_value(
                runtime_skill.get("restraint_types_by_pet") or {},
                server_runtime,
                target_pet_id,
            )
            if matched_target_key is None:
                matched_target_key = restraint_key

            base_power = _optional_int(breakdown.get("base_power") or (prediction or {}).get("power"))
            final_power = _optional_int(breakdown.get("final_power") or breakdown.get("effective_power"))
            runtime_power = _optional_int(breakdown.get("runtime_power"))
            strategy_totals = _mechanism_strategy_totals(
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
            decomp_total, decomp_delta, decomp_matches = _decomposition_check(
                runtime_skill,
                matched_damage_param,
            )

            yield DamageMechanismSample(
                session=session,
                round_num=event.round_num,
                event_index=event.index,
                skill_id=_optional_int(skill_id),
                skill_name=str(skill_name),
                target_side=target_side,
                target_pet_id=_optional_int(target_pet_id),
                actual_total=actual_total,
                predicted_total=_optional_int(predicted_total),
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
                matched_damage_param=_optional_int(matched_damage_param),
                restraint_type=_optional_int(restraint_type),
                runtime_state_source=runtime_source,
                runtime_pet_id=_optional_int((runtime_pet or {}).get("pet_id")),
                runtime_pet_name=(runtime_pet or {}).get("name"),
                raw_damage=_optional_int(runtime_skill.get("raw_damage")),
                rule_damage_param=_optional_int(runtime_skill.get("rule_damage_param")),
                effect_damage_param=_optional_int(runtime_skill.get("effect_damage_param")),
                buff_damage_param=_optional_int(runtime_skill.get("buff_damage_param")),
                ex_damage_param=_optional_int(runtime_skill.get("ex_damage_param")),
                damage_param_result=_optional_int(runtime_skill.get("damage_param_result")),
                damage_type=_optional_int(runtime_skill.get("damage_type")),
                cost_energy=_resolve_runtime_cost(runtime_skill),
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


def _ledger_records_for_damage(state: Dict[str, Any], detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    ledger = ((state.get("field_context") or {}).get("damage_ledger") or [])
    by_id = {
        str(item.get("ledger_id")): item
        for item in ledger
        if item.get("ledger_id")
    }
    wanted = [str(item) for item in detail.get("ledger_ids") or []]
    if detail.get("ledger_id") is not None:
        wanted.append(str(detail["ledger_id"]))
    wanted = list(dict.fromkeys(wanted))
    records = [by_id[item] for item in wanted if item in by_id]
    if records:
        return records
    skill_name = detail.get("skill_name")
    hp_after = detail.get("hp_after")
    candidates = [
        item for item in ledger
        if item.get("event_kind") == "damage"
        and item.get("skill_name") == skill_name
        and (hp_after is None or item.get("hp_after") == hp_after)
    ]
    return candidates[-1:] if candidates else []


def _ledger_actual_damage(item: Dict[str, Any]) -> int:
    if item.get("actual_damage") is not None:
        return max(0, int(item["actual_damage"]))
    if item.get("damage") is not None:
        return max(0, int(item["damage"]))
    before = item.get("hp_before")
    after = item.get("hp_after")
    if before is not None and after is not None:
        return max(0, int(before) - int(after))
    return 0


def _find_prediction(
    advice: Optional[Dict[str, Any]], skill_name: str, target_side: str,
) -> Optional[Dict[str, Any]]:
    if not advice:
        return None
    key = "skill_analysis" if target_side == "敌方" else "opp_skill_analysis"
    for pred in advice.get(key, []):
        if pred.get("skill_name") == skill_name:
            return pred
    return None


def _candidate_totals(
    predicted_total: Optional[int],
    prediction: Dict[str, Any],
    breakdown: Dict[str, Any],
) -> Dict[str, int]:
    if predicted_total is None:
        return {}
    out = {"production": int(predicted_total)}
    power = breakdown.get("final_power") or prediction.get("power")
    base_power = breakdown.get("base_power")
    if power and base_power and power != base_power:
        out["static_power_fallback"] = max(1, round(predicted_total * base_power / power))
    server_runtime = breakdown.get("server_runtime") or {}
    calc_eff = server_runtime.get("calc_effectiveness")
    display_eff = server_runtime.get("display_effectiveness")
    runtime_power = breakdown.get("runtime_power")
    if server_runtime.get("power_source") == "server_damage_params" and runtime_power and base_power:
        out["server_target_power_keep_restraint"] = max(1, round(predicted_total * runtime_power / base_power))
        if calc_eff and display_eff:
            out["server_target_power_no_restraint"] = max(
                1,
                round(out["server_target_power_keep_restraint"] / max(float(display_eff), 0.001)),
            )
    return out


def _mechanism_strategy_totals(
    predicted_total: Optional[int],
    prediction: Dict[str, Any],
    breakdown: Dict[str, Any],
    matched_damage_param: Any,
    restraint_type: Any,
) -> Dict[str, int]:
    out = _candidate_totals(predicted_total, prediction, breakdown)
    if predicted_total is None:
        return out
    final_power = _optional_int(breakdown.get("final_power") or breakdown.get("effective_power"))
    matched = _optional_int(matched_damage_param)
    if not final_power or not matched:
        return out
    out["damage_param_as_effective_power"] = max(1, round(int(predicted_total) * matched / final_power))
    restraint_mult = _restraint_to_multiplier(restraint_type)
    if restraint_mult:
        neutralized = matched / max(restraint_mult, 0.001)
        out["damage_param_neutralized_by_restraint"] = max(
            1,
            round(int(predicted_total) * neutralized / final_power),
        )
    return out


def _runtime_skill_for_sample(
    event: Any,
    target_side: str,
    skill_id: Any,
    breakdown: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], str]:
    for source, state in (("state_before", event.state_before), ("state_after", event.state_after)):
        runtime_skill, pet = _find_runtime_skill(state, target_side, skill_id)
        if runtime_skill:
            return runtime_skill, pet, source
    runtime_skill = breakdown.get("runtime_skill")
    if isinstance(runtime_skill, dict) and runtime_skill:
        return runtime_skill, None, "prediction_breakdown"
    return {}, None, "missing"


def _find_runtime_skill(
    state: Dict[str, Any],
    target_side: str,
    skill_id: Any,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    if skill_id is None:
        return {}, None
    keys = [str(skill_id), skill_id]
    seen: set[int] = set()
    for pet in _attacker_pet_candidates(state, target_side):
        marker = id(pet)
        if marker in seen:
            continue
        seen.add(marker)
        runtime = pet.get("skill_runtime") or {}
        for key in keys:
            item = runtime.get(key)
            if isinstance(item, dict):
                return item, pet
    return {}, None


def _attacker_pet_candidates(state: Dict[str, Any], target_side: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    if target_side == "敌方":
        candidate_specs = (("my_active", None), (None, "my_pets"))
    elif target_side == "我方":
        candidate_specs = (("opp_active", None), (None, "opp_pets"))
    else:
        candidate_specs = (
            ("my_active", None), ("opp_active", None),
            (None, "my_pets"), (None, "opp_pets"),
        )
    for active_key, list_key in candidate_specs:
        if active_key:
            pet = state.get(active_key)
            if isinstance(pet, dict):
                candidates.append(pet)
        if list_key:
            candidates.extend([pet for pet in state.get(list_key, []) if isinstance(pet, dict)])
    return candidates


def _matched_runtime_value(
    values_by_pet: Dict[Any, Any],
    server_runtime: Dict[str, Any],
    target_pet_id: Any,
) -> Tuple[Optional[str], Any]:
    if not values_by_pet:
        return None, None
    keys: List[str] = []
    for value in (server_runtime.get("matched_target_key"), target_pet_id):
        if value is not None:
            keys.append(str(value))
    for key in dict.fromkeys(keys):
        if values_by_pet.get(key) is not None:
            return key, values_by_pet[key]
    if str(target_pet_id) == "20000000" and len(values_by_pet) == 1:
        key, value = next(iter(values_by_pet.items()))
        return str(key), value
    return None, None


def _decomposition_check(
    runtime_skill: Dict[str, Any],
    matched_damage_param: Any,
) -> Tuple[Optional[int], Optional[int], Optional[bool]]:
    matched = _optional_int(matched_damage_param)
    if matched is None:
        return None, None, None
    fields = (
        "raw_damage", "rule_damage_param", "effect_damage_param",
        "buff_damage_param", "ex_damage_param",
    )
    parts = [_optional_int(runtime_skill.get(field)) for field in fields]
    if all(part is None for part in parts):
        return None, None, None
    total = sum(part or 0 for part in parts)
    delta = total - matched
    return total, delta, abs(delta) <= 1


def _mechanism_group_by_skill(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for sample in samples:
        grouped.setdefault(str(sample.get("skill_name") or "?"), []).append(sample)
    out: Dict[str, Dict[str, Any]] = {}
    for name, items in grouped.items():
        out[name] = {
            "total": len(items),
            "sessions": sorted({str(s.get("session")) for s in items if s.get("session")}),
            "strategy_compare": _mechanism_strategy_summary(items),
            "decomposition_checks": _decomposition_summary(items),
            "field_presence": _field_presence(items),
        }
        out[name]["recommendation"] = _mechanism_recommendation(items, out[name])
    return dict(sorted(out.items(), key=lambda item: item[1]["total"], reverse=True))


def _mechanism_strategy_summary(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Tuple[int, float]]] = {}
    for sample in samples:
        actual = _optional_int(sample.get("actual_total"))
        if actual is None:
            continue
        for name, total in (sample.get("strategy_totals") or {}).items():
            candidate = _optional_int(total)
            if candidate is None:
                continue
            error = abs(candidate - actual)
            grouped.setdefault(name, []).append((error, error / max(1, actual)))
    return {
        name: {
            "samples": len(values),
            "mae": round(mean(error for error, _ in values), 2) if values else None,
            "mape": round(mean(pct for _, pct in values), 4) if values else None,
        }
        for name, values in sorted(grouped.items())
    }


def _decomposition_summary(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    checked = [s for s in samples if s.get("decomposition_matches") is not None]
    deltas = [
        abs(int(s["decomposition_delta"]))
        for s in checked
        if s.get("decomposition_delta") is not None
    ]
    return {
        "checked": len(checked),
        "matched": sum(1 for s in checked if s.get("decomposition_matches") is True),
        "match_rate": round(
            sum(1 for s in checked if s.get("decomposition_matches") is True) / len(checked),
            4,
        ) if checked else None,
        "mae_delta": round(mean(deltas), 2) if deltas else None,
    }


def _field_presence(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    fields = (
        "raw_damage", "rule_damage_param", "effect_damage_param",
        "buff_damage_param", "ex_damage_param", "damage_param_result",
        "matched_damage_param", "restraint_type", "damage_type", "cost_energy",
        "set_cost_info", "skill_buff", "enhance_info", "cr_damage_params",
        "extra_damage_type",
    )
    total = len(samples)
    return {
        field: {
            "count": sum(1 for sample in samples if _has_value(sample.get(field))),
            "rate": round(
                sum(1 for sample in samples if _has_value(sample.get(field))) / total,
                4,
            ) if total else None,
        }
        for field in fields
    }


def _mechanism_recommendation(
    samples: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    if len(samples) < 3:
        return {"status": "insufficient_samples", "reason": "matched direct damage samples below 3"}
    skill_ids = {sample.get("skill_id") for sample in samples if sample.get("skill_id") is not None}
    if 7060130 in skill_ids:
        return {
            "status": "audit_only",
            "reason": "confirmed light special damage; child effects settle after base damage",
        }
    strategies = summary.get("strategy_compare") or {}
    production = strategies.get("production") or {}
    production_mape = production.get("mape")
    damage_candidates = {
        name: item for name, item in strategies.items()
        if name in {"damage_param_as_effective_power", "damage_param_neutralized_by_restraint"}
        and item.get("samples", 0) >= 3
        and item.get("mape") is not None
    }
    if not damage_candidates or production_mape is None:
        return {"status": "audit_only", "reason": "damage-param candidates are not comparable yet"}
    best_name, best = min(damage_candidates.items(), key=lambda item: item[1]["mape"])
    if best["mape"] <= production_mape * 0.85:
        status = "likely_effective_param" if best_name == "damage_param_as_effective_power" else "candidate_for_whitelist"
        return {
            "status": status,
            "reason": f"{best_name} improves MAPE from {production_mape} to {best['mape']}",
            "best_strategy": best_name,
        }
    return {
        "status": "audit_only",
        "reason": "damage-param candidates do not materially improve production",
    }


def _first_present(items: List[Dict[str, Any]], key: str) -> Any:
    for item in items:
        if item.get(key) is not None:
            return item[key]
    return None


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _has_value(value: Any) -> bool:
    return value not in (None, {}, [])


def _resolve_runtime_cost(runtime_skill: Dict[str, Any]) -> Optional[int]:
    for key in ("cost_energy_result", "cost_energy", "raw_cost_energy"):
        if runtime_skill.get(key) is not None:
            return _optional_int(runtime_skill[key])
    return None


def _restraint_to_multiplier(value: Any) -> Optional[float]:
    ivalue = _optional_int(value)
    if ivalue is None:
        return None
    return {
        -2: 0.25,
        -1: 0.5,
        0: 1.0,
        1: 1.5,
        2: 2.0,
        3: 4.0,
    }.get(ivalue)
