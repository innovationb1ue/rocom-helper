"""能量监控钩子 — 追踪能量状态，预测耗尽时机，识别攻击窗口。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.hook_registry import AnalysisHook, HookAdvice, HookContext, HookSignal, HookTrigger
from src.analysis.hooks.energy_advice import (
    build_my_energy_messages,
    build_opp_energy_messages,
    energy_advice_priority,
    should_avoid_skill,
)


class EnergyMonitorHook(AnalysisHook):
    """监控双方能量状态，提供能量管理建议。"""

    @property
    def hook_id(self) -> str:
        return "energy_monitor"

    @property
    def triggers(self) -> List[HookTrigger]:
        return [
            HookTrigger.ON_ACTION_RESOLVE,
            HookTrigger.ON_ROUND_START,
            HookTrigger.ON_SPECIAL_REFRESH,
        ]

    def __init__(self) -> None:
        self._reset_state()

    def _reset_state(self) -> None:
        self._opp_energy_log: List[Dict[str, Any]] = []
        self._my_energy_log: List[Dict[str, Any]] = []

    def reset(self) -> None:
        self._reset_state()

    def on_battle_enter(self, ctx: HookContext) -> None:
        self._reset_state()

    def process(self, ctx: HookContext) -> Optional[HookAdvice]:
        my_active = ctx.state.get("my_active")
        opp_active = ctx.state.get("opp_active")
        messages: List[Dict[str, str]] = []

        if my_active:
            my_energy = my_active.get("energy", 5)
            self._my_energy_log.append({"round": ctx.round_num, "energy": my_energy})
            messages.extend(build_my_energy_messages(my_active))

        if opp_active:
            opp_energy = opp_active.get("energy", 5)
            self._opp_energy_log.append({"round": ctx.round_num, "energy": opp_energy})
            messages.extend(build_opp_energy_messages(opp_active, self._opp_energy_log))

        if not messages:
            return None

        return HookAdvice(
            hook_id=self.hook_id,
            priority=energy_advice_priority(messages),
            title="能量监控",
            messages=messages,
        )

    def emit_signals(self, ctx: HookContext) -> List[HookSignal]:
        """能量不足时发出 avoid_skill 信号。"""
        my_active = ctx.state.get("my_active")
        if not my_active:
            return []

        if should_avoid_skill(my_active):
            return [HookSignal(
                hook_id=self.hook_id,
                signal_type="avoid_skill",
                target=None,
                strength=0.9,
            )]
        return []
