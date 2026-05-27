"""Shared data models for battle analysis outputs."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.analysis.event_formatter import FormattedEvent


@dataclass
class ProcessResult:
    """All computed outputs for one battle event."""
    state: Dict[str, Any]
    formatted_events: List[FormattedEvent] = field(default_factory=list)
    battle_advice: Optional[Dict[str, Any]] = None
    hook_advice: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, str]] = field(default_factory=list)
    tactical: Optional[Dict[str, Any]] = None


@dataclass
class SkillAnalysis:
    skill_id: int
    skill_name: str
    equipped_slot: int
    skill_element: int
    skill_damage_type: int
    energy_cost: int
    skill_desc: Optional[str] = None
    power: Optional[int] = None
    effective_power: Optional[int] = None
    expected_damage: Optional[int] = None
    min_damage: Optional[int] = None
    max_damage: Optional[int] = None
    total_min_damage: Optional[int] = None
    total_max_damage: Optional[int] = None
    effectiveness: Optional[float] = None
    effectiveness_label: Optional[str] = None
    is_stab: Optional[bool] = None
    can_ko: Optional[bool] = None
    hit_count: int = 1
    confidence: Optional[str] = None
    power_mult: Optional[float] = None
    weather_mult: Optional[float] = None
    damage_breakdown: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)
    prediction: Optional[Dict[str, Any]] = None
    explain: Optional[Dict[str, Any]] = None
    validation_hint: Optional[str] = None
    _quality_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BattleAdvice:
    skill_analysis: List[SkillAnalysis] = field(default_factory=list)
    suggestions: List[Dict[str, str]] = field(default_factory=list)
    traits: List[Dict[str, str]] = field(default_factory=list)
    opp_traits: List[Dict[str, str]] = field(default_factory=list)
    opp_skill_analysis: List[SkillAnalysis] = field(default_factory=list)
    opp_skill_source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_analysis": [s.to_dict() for s in self.skill_analysis],
            "suggestions": self.suggestions,
            "traits": self.traits,
            "opp_traits": self.opp_traits,
            "opp_skill_analysis": [s.to_dict() for s in self.opp_skill_analysis],
            "opp_skill_source": self.opp_skill_source,
        }


@dataclass
class OpponentAction:
    action_type: str
    skill_id: Optional[int] = None
    skill_name: Optional[str] = None
    switch_to_name: Optional[str] = None
    probability: float = 0.0
    source: str = ""
    reason: str = ""
    threat_damage: Optional[int] = None
    can_ko: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResolvedOutcome:
    our_damage_dealt: int = 0
    opp_damage_dealt: int = 0
    we_ko: bool = False
    opp_kos_us: bool = False
    we_act_first: bool = True
    our_remaining_hp: int = 0
    opp_remaining_hp: int = 0
    type_matchup_after: float = 1.0
    energy_after: int = 0
    pet_count_delta: int = 0
    incoming_energy: int = 0
    incoming_has_buffs: bool = False


@dataclass
class ActionScore:
    action_type: str
    skill_id: Optional[int] = None
    skill_name: Optional[str] = None
    switch_to_name: Optional[str] = None
    score: float = 0.0
    reason: str = ""
    category: str = "balanced"
    expected_gain: str = ""
    risk: str = ""
    confidence: str = "medium"
    damage_dealt: Optional[int] = None
    damage_taken: Optional[int] = None
    can_ko: bool = False
    energy_cost: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)
    unknowns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TacticalRecommendation:
    actions: List[ActionScore] = field(default_factory=list)
    opp_predicted: List[OpponentAction] = field(default_factory=list)
    round_number: int = 0
    confidence: str = "medium"
    primary_plan: str = ""
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    reliability: Dict[str, Any] = field(default_factory=dict)
    opponent_profile: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actions": [a.to_dict() for a in self.actions],
            "opp_predicted": [o.to_dict() for o in self.opp_predicted],
            "round_number": self.round_number,
            "confidence": self.confidence,
            "primary_plan": self.primary_plan,
            "warnings": self.warnings,
            "metrics": self.metrics,
            "reliability": self.reliability,
            "opponent_profile": self.opponent_profile,
        }
