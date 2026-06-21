"""对手行为追踪钩子 — 记录对手技能使用、换宠模式，识别偏好策略。"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from src.analysis.hook_registry import AnalysisHook, HookAdvice, HookContext, HookTrigger
from src.analysis.constants import OPCODE_ACTION_RESOLVE, OPCODE_ROUND_START
from src.analysis.hooks.opponent_behavior import (
    append_switch_logs,
    build_behavior_data,
    build_behavior_messages,
)


class OpponentTrackerHook(AnalysisHook):
    """追踪对手行为模式：技能使用频率、换宠时机、未曝光技能。"""

    @property
    def hook_id(self) -> str:
        return "opponent_tracker"

    @property
    def triggers(self) -> List[HookTrigger]:
        return [
            HookTrigger.ON_ACTION_RESOLVE,
            HookTrigger.ON_BATTLE_ENTER,
            HookTrigger.ON_CHANGE_PET,
        ]

    def __init__(self) -> None:
        self._reset_state()

    def _reset_state(self) -> None:
        self._opp_skill_counts: Dict[str, Counter] = {}  # pet_name -> {skill_name: count}
        self._opp_switch_log: List[Dict[str, Any]] = []
        self._total_rounds: int = 0
        self._last_switch_key: Optional[tuple] = None

    def reset(self) -> None:
        self._reset_state()

    def on_battle_enter(self, ctx: HookContext) -> None:
        self._reset_state()

    def process(self, ctx: HookContext) -> Optional[HookAdvice]:
        messages: List[Dict[str, str]] = []

        if ctx.opcode == OPCODE_ROUND_START:
            self._total_rounds = ctx.round_num

        if ctx.opcode == OPCODE_ACTION_RESOLVE:
            opp_active = ctx.state.get("opp_active") or {}
            messages = build_behavior_messages(
                ctx.entries,
                opp_active,
                self._opp_skill_counts,
                self._opp_switch_log,
            )
            self._last_switch_key = append_switch_logs(
                ctx.entries,
                self._opp_switch_log,
                self._last_switch_key,
                ctx.round_num,
                opp_active,
            )

        if not messages:
            return None

        return HookAdvice(
            hook_id=self.hook_id,
            priority=2,
            title="对手行为分析",
            messages=messages,
            data=build_behavior_data(
                self._opp_skill_counts,
                self._opp_switch_log,
                self._total_rounds,
            ),
        )
