"""无头战斗回放运行器 — 纯后端自闭环回放、分析、验证。

BattleReplayRunner 将 packets 馈入 BattleProcessor，
收集每个事件的 ProcessResult 到结构化的 ReplayResult 中。

用法:
    runner = BattleReplayRunner()
    result = runner.run(packets)        # packets 来自 load_battle_packets()
    print(result.final_state["round"])
    for rs in result.rounds:
        for pred in rs.damage_predictions:
            print(pred["skill_name"], pred["expected_damage"])
"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.analysis.battle_processor import BattleProcessor
from src.analysis.battle_summary import compute_battle_summary
from src.analysis.models import ProcessResult
from src.analysis.constants import OPCODE_ACTION_RESOLVE, OPCODE_ROUND_START
from src.analysis.replay_messages import build_battle_messages
from src.protocol.opcodes import summarize
from src.protocol.proto_core import extract_inner_message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# BattleReplayRunner
# ---------------------------------------------------------------------------
class BattleReplayRunner:
    """无头回放运行器。不依赖 FastAPI、WebSocket 或前端。"""

    def __init__(
        self,
        *,
        include_analysis: bool = True,
        include_hooks: bool = True,
        include_formatting: bool = True,
    ) -> None:
        self._include_analysis = include_analysis
        self._include_hooks = include_hooks
        self._include_formatting = include_formatting

    def run(
        self,
        packets: List[Dict[str, Any]],
        stop_round: Optional[int] = None,
    ) -> ReplayResult:
        processor = BattleProcessor(
            include_analysis=self._include_analysis,
            include_hooks=self._include_hooks,
            include_formatting=self._include_formatting,
        )
        event_snapshots: List[ReplayEventSnapshot] = []
        round_map: Dict[int, RoundSnapshot] = {}
        message_sequence: List[Dict[str, Any]] = []
        current_round = 0
        stopped_early = False

        for idx, item in enumerate(packets):
            record = item["record"]
            opcode = item["opcode"]

            inner = None
            if opcode == 0x0414:
                inner = extract_inner_message(record.get("root", {}))

            kind, summary = summarize(record, inner)
            detail = summary.get("detail", summary)
            if detail is None:
                detail = {}

            state_before = copy.deepcopy(processor.get_state())
            result = processor.process_event(opcode, detail)
            state_after = result.state

            current_round = state_after.get("round", current_round)

            # Formatting
            formatted_dicts: List[Dict[str, Any]] = []
            if self._include_formatting:
                formatted_dicts = [copy.deepcopy(e.to_dict()) for e in result.formatted_events]

            # Analysis (already computed by processor, just include/exclude)
            battle_advice_dict: Optional[Dict[str, Any]] = None
            if self._include_analysis:
                battle_advice_dict = copy.deepcopy(result.battle_advice)

            # Hooks (already computed by processor, just include/exclude)
            hook_advice_dicts: List[Dict[str, Any]] = []
            if self._include_hooks:
                hook_advice_dicts = copy.deepcopy(result.hook_advice)

            # Suggestions
            suggestions = copy.deepcopy(result.suggestions)
            filtered_result = ProcessResult(
                state=state_after,
                formatted_events=result.formatted_events if self._include_formatting else [],
                battle_advice=battle_advice_dict,
                hook_advice=hook_advice_dicts,
                suggestions=suggestions,
                tactical=copy.deepcopy(result.tactical) if self._include_analysis else None,
            )
            messages = build_battle_messages(opcode, filtered_result)
            message_sequence.extend(messages)

            snap = ReplayEventSnapshot(
                index=idx,
                opcode=opcode,
                kind=kind,
                round_num=current_round,
                state_before=state_before,
                state_after=state_after,
                formatted_events=formatted_dicts,
                battle_advice=battle_advice_dict,
                hook_advice=hook_advice_dicts,
                suggestions=suggestions,
                tactical=filtered_result.tactical,
                messages=messages,
            )
            event_snapshots.append(snap)

            # Round aggregation
            if current_round not in round_map:
                round_map[current_round] = RoundSnapshot(
                    round_num=current_round,
                    state_at_start=state_before,
                )
            rs = round_map[current_round]
            rs.events.append(snap)
            rs.state_at_end = state_after
            rs.formatted_events.extend(formatted_dicts)
            rs.suggestions.extend(suggestions)
            rs.messages.extend(messages)
            if battle_advice_dict:
                rs.battle_advice = battle_advice_dict
                rs.damage_predictions = battle_advice_dict.get("skill_analysis", [])
                rs.traits = battle_advice_dict.get("traits", [])
                rs.opp_traits = battle_advice_dict.get("opp_traits", [])
                opp_skill_analysis = battle_advice_dict.get("opp_skill_analysis", [])
                if opp_skill_analysis:
                    rs.opp_skill_analysis = opp_skill_analysis
                    rs.opp_skill_source = battle_advice_dict.get("opp_skill_source", "")
            if filtered_result.tactical:
                rs.tactical_recommendations = filtered_result.tactical

            # Stop early check
            if stop_round is not None and current_round >= stop_round and opcode in (OPCODE_ACTION_RESOLVE, OPCODE_ROUND_START):
                stopped_early = True
                break

        final_state = processor.get_state()
        battle_summary = compute_battle_summary(final_state)
        rounds = [round_map[r] for r in sorted(round_map.keys())]

        return ReplayResult(
            total_packets=len(event_snapshots),
            events=event_snapshots,
            rounds=rounds,
            final_state=final_state,
            battle_summary=battle_summary,
            stopped_early=stopped_early,
            messages=message_sequence,
        )
