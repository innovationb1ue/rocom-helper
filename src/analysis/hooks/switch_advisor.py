"""换宠建议钩子 — 基于属性克制和威胁评估推荐换宠时机。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.analysis.hook_registry import AnalysisHook, HookAdvice, HookContext, HookSignal, HookTrigger
from src.analysis.constants import OPCODE_ACTION_RESOLVE
from src.analysis.counter import CounterPicker
from src.analysis.pet_identity import same_battle_pet
from src.game.type_chart import TypeChart

logger = logging.getLogger(__name__)


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

    # 换宠建议逻辑:
    # 1. 当前对局不利（对手克制 >=2x，我方 <=1x）→ 找最佳 counter
    # 2. 对手换宠后 → 重新评估对局，推荐克制精灵
    # counter 评分 = offensive_effectiveness * (1 / defensive_effectiveness)
    def process(self, ctx: HookContext) -> Optional[HookAdvice]:
        my_active = ctx.state.get("my_active")
        opp_active = ctx.state.get("opp_active")
        my_pets = ctx.state.get("my_pets", [])
        if not my_active or not opp_active or not my_pets:
            return None

        opp_types = opp_active.get("types", [])
        my_types = my_active.get("types", [])
        if not opp_types:
            return None

        messages: List[Dict[str, str]] = []

        # Check if current matchup is unfavorable
        my_offensive = self._best_effectiveness(my_types, opp_types)
        opp_offensive = self._best_effectiveness(opp_types, my_types)

        if opp_offensive >= 2.0 and my_offensive <= 1.0:
            # Bad matchup — find a better pet
            best_switch = self._find_best_counter(my_pets, opp_active)
            if best_switch:
                pet_name = best_switch.get("name", "未知")
                best_eff = self._best_effectiveness(
                    best_switch.get("types", []), opp_types,
                )
                messages.append({
                    "type": "bad_matchup",
                    "message": (
                        f"当前对局不利（{opp_active.get('name', '对手')}克制我方），"
                        f"建议换上 {pet_name}（克制 x{best_eff}）"
                    ),
                })

        # On opponent switch, analyze new matchup
        is_opp_switch = False
        if ctx.opcode == OPCODE_ACTION_RESOLVE:
            for entry in ctx.entries:
                if entry.get("kind") == "change_pet":
                    side_val = entry.get("target_side", entry.get("actor_side"))
                    if isinstance(side_val, str):
                        is_opp = side_val != "我方"
                    else:
                        is_opp = side_val is not None and int(side_val) >= 401
                    if is_opp:
                        is_opp_switch = True

        if is_opp_switch and not messages:
            best_switch = self._find_best_counter(my_pets, opp_active)
            if best_switch and not same_battle_pet(best_switch, my_active):
                pet_name = best_switch.get("name", "未知")
                best_eff = self._best_effectiveness(
                    best_switch.get("types", []), opp_types,
                )
                if best_eff >= 2.0:
                    messages.append({
                        "type": "counter_switch",
                        "message": (
                            f"对手换上了 {opp_active.get('name', '新精灵')}，"
                            f"建议换上 {pet_name} 进行克制（x{best_eff}）"
                        ),
                    })

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

        opp_types = opp_active.get("types", [])
        my_types = my_active.get("types", [])
        if not opp_types:
            return []

        my_offensive = self._best_effectiveness(my_types, opp_types)
        opp_offensive = self._best_effectiveness(opp_types, my_types)

        signals: List[HookSignal] = []
        if opp_offensive >= 2.0 and my_offensive <= 1.0:
            best_switch = self._find_best_counter(
                ctx.state.get("my_pets", []), opp_active,
            )
            if best_switch:
                signals.append(HookSignal(
                    hook_id=self.hook_id,
                    signal_type="prefer_switch",
                    target=best_switch.get("name"),
                    strength=0.8,
                ))
        return signals

    def _best_effectiveness(
        self, attack_types: List[int], defend_types: List[int],
    ) -> float:
        best = 1.0
        for at in attack_types:
            eff = self._chart.get_multiplier(at, defend_types)
            if eff > best:
                best = eff
        return best

    def _find_best_counter(
        self, my_pets: List[Dict[str, Any]], opp_pet: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        opp_types = opp_pet.get("types", [])
        if not opp_types:
            return None

        living = [
            p for p in my_pets
            if p.get("current_hp", 1) > 0 and not same_battle_pet(p, opp_pet)
        ]
        if not living:
            return None

        norm_opp = {"types": opp_types}
        norm_living = [
            {
                "types": p.get("types", []),
                "pet_id": p.get("pet_id"),
                "name": p.get("name"),
                "slot": p.get("slot"),
                "side": p.get("side"),
                "base_conf_id": p.get("base_conf_id"),
                "battle_uid": p.get("battle_uid"),
            }
            for p in living
        ]
        counters = self._counter.find_counters([norm_opp], norm_living, top_n=1)
        if counters:
            counter = counters[0]
            for p in living:
                if same_battle_pet(p, counter):
                    return p
        return None
