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
from typing import Any, Dict, List, Optional

from src.analysis.battle_processor import BattleProcessor
from src.analysis.battle_summary import compute_battle_summary
from src.analysis.replay_flow import (
    build_replay_messages,
    extract_replay_detail,
    filter_process_result,
    make_event_snapshot,
    should_stop_replay,
    update_round_snapshot,
)
from src.analysis.replay_models import ReplayEventSnapshot, ReplayResult, RoundSnapshot

logger = logging.getLogger(__name__)


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

            kind, detail = extract_replay_detail(record, opcode)
            state_before = copy.deepcopy(processor.get_state())
            result = processor.process_event(opcode, detail)
            state_after = result.state

            current_round = state_after.get("round", current_round)
            (
                filtered_result,
                formatted_dicts,
                battle_advice_dict,
                hook_advice_dicts,
                suggestions,
            ) = filter_process_result(
                result,
                include_analysis=self._include_analysis,
                include_hooks=self._include_hooks,
                include_formatting=self._include_formatting,
            )
            messages = build_replay_messages(opcode, filtered_result)
            message_sequence.extend(messages)

            snap = make_event_snapshot(
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

            update_round_snapshot(
                round_map,
                round_num=current_round,
                state_before=state_before,
                state_after=state_after,
                event=snap,
                battle_advice=battle_advice_dict,
                formatted_events=formatted_dicts,
                suggestions=suggestions,
                messages=messages,
                tactical=filtered_result.tactical,
            )

            if should_stop_replay(stop_round, current_round, opcode):
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
