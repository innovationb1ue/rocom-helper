"""换宠建议钩子 — 基于属性克制和威胁评估推荐换宠时机。"""
from __future__ import annotations

from typing import List, Optional

from src.analysis.hook_registry import AnalysisHook, HookAdvice, HookContext, HookSignal, HookTrigger
from src.analysis.counter import CounterPicker
from src.analysis.hooks.switch_advice import build_switch_messages, prefer_switch_target
from src.game.type_chart import TypeChart


class SwitchAdvisorHook(AnalysisHook):
    """当属性不利或对手换宠时，推荐最佳应对宠物。"""

    @property
    def hook_id(self) -> str:
        return "switch_advisor"

    @property
    def triggers(self) -> List[HookTrigger]:
        return [HookTrigger.ON_ROUND_START, HookTrigger.ON_CHANGE_PET]

    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self._chart = type_chart or TypeChart()
        self._counter = CounterPicker(self._chart)

    def on_battle_enter(self, ctx: HookContext) -> None:
        pass

    def process(self, ctx: HookContext) -> Optional[HookAdvice]:
        my_active = ctx.state.get("my_active")
        opp_active = ctx.state.get("opp_active")
        my_pets = ctx.state.get("my_pets", [])
        if not my_active or not opp_active or not my_pets:
            return None

        messages = build_switch_messages(
            self._chart,
            self._counter,
            my_active,
            opp_active,
            my_pets,
            ctx.opcode,
            ctx.entries,
        )
        if not messages:
            return None

        return HookAdvice(
            hook_id=self.hook_id,
            priority=1,
            title="换宠建议",
            messages=messages,
        )

    def emit_signals(self, ctx: HookContext) -> List[HookSignal]:
        """检测到不利对位时发出 prefer_switch 信号。"""
        my_active = ctx.state.get("my_active")
        opp_active = ctx.state.get("opp_active")
        if not my_active or not opp_active:
            return []

        best_switch = prefer_switch_target(
            self._chart,
            self._counter,
            my_active,
            opp_active,
            ctx.state.get("my_pets", []),
        )
        if not best_switch:
            return []

        return [HookSignal(
            hook_id=self.hook_id,
            signal_type="prefer_switch",
            target=best_switch.get("name"),
            strength=0.8,
        )]
