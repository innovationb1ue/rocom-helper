"""无头回放结果模型。

这些 dataclass 是 BattleReplayRunner 的公开结果契约，独立放置后可被
审计、报告和单元测试模块复用，而不需要导入回放执行器。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ReplayEventSnapshot:
    index: int
    opcode: int
    kind: str
    round_num: int
    state_before: Dict[str, Any]
    state_after: Dict[str, Any]
    formatted_events: List[Dict[str, Any]] = field(default_factory=list)
    battle_advice: Optional[Dict[str, Any]] = None
    hook_advice: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, str]] = field(default_factory=list)
    tactical: Optional[Dict[str, Any]] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RoundSnapshot:
    round_num: int
    events: List[ReplayEventSnapshot] = field(default_factory=list)
    state_at_start: Dict[str, Any] = field(default_factory=dict)
    state_at_end: Dict[str, Any] = field(default_factory=dict)
    battle_advice: Optional[Dict[str, Any]] = None
    damage_predictions: List[Dict[str, Any]] = field(default_factory=list)
    formatted_events: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, str]] = field(default_factory=list)
    traits: List[Dict[str, Any]] = field(default_factory=list)
    opp_traits: List[Dict[str, Any]] = field(default_factory=list)
    opp_skill_analysis: List[Dict[str, Any]] = field(default_factory=list)
    opp_skill_source: str = ""
    tactical_recommendations: Optional[Dict[str, Any]] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReplayResult:
    total_packets: int
    events: List[ReplayEventSnapshot] = field(default_factory=list)
    rounds: List[RoundSnapshot] = field(default_factory=list)
    final_state: Dict[str, Any] = field(default_factory=dict)
    battle_summary: Dict[str, Any] = field(default_factory=dict)
    stopped_early: bool = False
    messages: List[Dict[str, Any]] = field(default_factory=list)
