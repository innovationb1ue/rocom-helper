"""换宠建议钩子 — 基于属性克制和威胁评估推荐换宠时机。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.analysis.hook_registry import AnalysisHook, HookAdvice, HookContext, HookTrigger
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
        if ctx.opcode == 0x1324:
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
            if best_switch and best_switch.get("pet_id") != my_active.get("pet_id"):
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

        best_pet = None
        best_score = 0.0
        for pet in my_pets:
            if pet.get("current_hp", 1) <= 0:
                continue
            pet_types = pet.get("types", [])
            if not pet_types:
                continue
            offensive = self._best_effectiveness(pet_types, opp_types)
            defensive = 1.0 / max(0.25, self._best_effectiveness(opp_types, pet_types))
            score = offensive * defensive
            if score > best_score:
                best_score = score
                best_pet = pet

        return best_pet if best_score > 1.5 else None
