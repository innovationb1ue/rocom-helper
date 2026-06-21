"""Damage audit sample data contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


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
