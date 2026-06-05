"""Typed contracts shared by analysis, replay, and WebSocket message builders.

运行时仍然使用 dict 以保持现有 API/WebSocket 兼容；这里用 TypedDict 把
跨模块消息形状集中声明，作为后续 dataclass/schema 化的过渡层。
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, NotRequired, TypedDict, Union


class BattleBuffContract(TypedDict, total=False):
    id: int
    name: str
    stage: int | None
    source_skill: str | None
    turns_applied: int
    modifiers: Dict[str, float]
    modifier_summary: List[str]


class BattlePetContract(TypedDict, total=False):
    pet_id: int
    name: str
    types: List[int]
    current_hp: int
    max_hp: int
    hp_pct: float
    energy: int
    buffs: List[BattleBuffContract]
    level: int
    slot: int
    base_id: int
    base_conf_id: int
    side: int | str
    base_speed: int
    effective_speed: int | None
    battle_uid: str
    equipped_skills: List[Dict[str, Any]]
    skills: List[Dict[str, Any]]


class BattleStateContract(TypedDict, total=False):
    battle_id: int | None
    battle_mode: int | None
    round: int
    max_round: int
    weather: Dict[str, Any]
    field_context: Dict[str, Any]
    phase: str
    my_pets: List[BattlePetContract]
    opp_pets: List[BattlePetContract]
    my_active: BattlePetContract | None
    opp_active: BattlePetContract | None
    events: List[Dict[str, Any]]
    result: str | None
    suggestions: List[Dict[str, str]]


class ConnectedMessage(TypedDict):
    type: Literal["connected"]
    message: str


class StateUpdateMessage(TypedDict):
    type: Literal["state_update"]
    state: BattleStateContract


class BattleEventMessage(TypedDict):
    type: Literal["battle_event"]
    event: Dict[str, Any]


class BattleEventsMessage(TypedDict):
    type: Literal["battle_events"]
    events: List[Dict[str, Any]]


class SuggestionsMessage(TypedDict):
    type: Literal["suggestions"]
    suggestions: List[Dict[str, str]]


class BattleSummaryMessage(TypedDict):
    type: Literal["battle_summary"]
    summary: Dict[str, Any]


class SkillAnalysisMessage(TypedDict):
    type: Literal["skill_analysis"]
    skills: List[Dict[str, Any]]
    traits: List[Dict[str, Any]]
    opp_traits: List[Dict[str, Any]]
    opp_skill_analysis: List[Dict[str, Any]]
    opp_skill_source: str


class HookAdviceMessage(TypedDict):
    type: Literal["hook_advice"]
    advice: List[Dict[str, Any]]


class TacticalRecommendationsMessage(TypedDict):
    type: Literal["tactical_recommendations"]
    actions: List[Dict[str, Any]]
    opp_predicted: List[Dict[str, Any]]
    round_number: int
    confidence: str
    primary_plan: NotRequired[str]
    warnings: NotRequired[List[str]]
    metrics: NotRequired[Dict[str, Any]]
    reliability: NotRequired[Dict[str, Any]]
    opponent_profile: NotRequired[Dict[str, Any]]


BattleWebSocketMessage = Union[
    ConnectedMessage,
    StateUpdateMessage,
    BattleEventMessage,
    BattleEventsMessage,
    SuggestionsMessage,
    BattleSummaryMessage,
    SkillAnalysisMessage,
    HookAdviceMessage,
    TacticalRecommendationsMessage,
]
