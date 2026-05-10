"""能量监控钩子 — 追踪能量状态，预测耗尽时机，识别攻击窗口。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.analysis.hook_registry import AnalysisHook, HookAdvice, HookContext, HookTrigger

logger = logging.getLogger(__name__)


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

    # 能量分析逻辑:
    # 我方: 能量 <=1 且最低攻击技能需要 >1 → 能量枯竭警告
    # 我方: 能量不足以使用最强技能 → 低能量提示
    # 对手: 能量突然下降且 <=2 → 攻击窗口提示
    def process(self, ctx: HookContext) -> Optional[HookAdvice]:
        my_active = ctx.state.get("my_active")
        opp_active = ctx.state.get("opp_active")
        messages: List[Dict[str, str]] = []

        if my_active:
            my_energy = my_active.get("energy", 5)
            self._my_energy_log.append({"round": ctx.round_num, "energy": my_energy})
            equipped = my_active.get("equipped_skills") or my_active.get("used_skills") or []
            min_cost = self._min_attack_cost(equipped)
            if my_energy <= 1 and min_cost > 1:
                messages.append({
                    "type": "energy_starved",
                    "message": f"我方能量仅剩 {my_energy}，无法使用攻击技能，考虑能量瓶或低耗技能",
                })
            elif my_energy <= 3 and min_cost > my_energy:
                messages.append({
                    "type": "energy_low",
                    "message": f"我方能量 {my_energy} 不足以使用最强技能（需 {min_cost}）",
                })

        if opp_active:
            opp_energy = opp_active.get("energy", 5)
            self._opp_energy_log.append({"round": ctx.round_num, "energy": opp_energy})
            if opp_energy <= 2 and len(self._opp_energy_log) >= 2:
                prev_energy = self._opp_energy_log[-2].get("energy", 5)
                if prev_energy > opp_energy:
                    messages.append({
                        "type": "opp_energy_low",
                        "message": "对手能量可能不足，可趁机强攻",
                    })

        if not messages:
            return None

        return HookAdvice(
            hook_id=self.hook_id,
            priority=1 if any(m["type"] == "energy_starved" for m in messages) else 2,
            title="能量监控",
            messages=messages,
        )

    @staticmethod
    def _min_attack_cost(equipped: List[Dict[str, Any]]) -> int:
        min_cost = 99
        for eq in equipped:
            cost = eq.get("cost_energy")
            if cost is None:
                continue
            damage_type = eq.get("skill_damage_type", 0)
            if damage_type in (2, 3):
                min_cost = min(min_cost, cost)
        return min_cost if min_cost < 99 else 0
