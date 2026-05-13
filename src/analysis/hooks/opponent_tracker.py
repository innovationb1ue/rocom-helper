"""对手行为追踪钩子 — 记录对手技能使用、换宠模式，识别偏好策略。"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from src.analysis.hook_registry import AnalysisHook, HookAdvice, HookContext, HookTrigger
from src.analysis.constants import OPCODE_ACTION_RESOLVE, OPCODE_ROUND_START

logger = logging.getLogger(__name__)


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

    def reset(self) -> None:
        self._reset_state()

    def on_battle_enter(self, ctx: HookContext) -> None:
        self._reset_state()

    # 追踪逻辑:
    # 1. 记录对手每次技能使用 → 累计频率
    # 2. 使用 >=3 次且偏好技能占比 >=50% → 偏好提示
    # 3. 对手换宠记录 → 低HP换宠模式检测
    def process(self, ctx: HookContext) -> Optional[HookAdvice]:
        messages: List[Dict[str, str]] = []

        if ctx.opcode == OPCODE_ROUND_START:
            self._total_rounds = ctx.round_num

        if ctx.opcode == OPCODE_ACTION_RESOLVE:
            messages = self._process_action(ctx)

        if ctx.opcode == OPCODE_ACTION_RESOLVE:
            for entry in ctx.entries:
                if entry.get("kind") == "change_pet":
                    new_name = entry.get("new_pet_name", "?")
                    opp_active = ctx.state.get("opp_active", {})
                    hp_pct = opp_active.get("hp_pct", 1.0)
                    self._opp_switch_log.append({
                        "round": ctx.round_num,
                        "new_pet": new_name,
                        "prev_hp_pct": round(hp_pct, 2),
                    })

        if not messages:
            return None

        return HookAdvice(
            hook_id=self.hook_id,
            priority=2,
            title="对手行为分析",
            messages=messages,
            data={
                "skill_history": {
                    k: dict(v) for k, v in self._opp_skill_counts.items()
                },
                "switch_log": self._opp_switch_log,
                "total_rounds": self._total_rounds,
            },
        )

    def _process_action(self, ctx: HookContext) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        for entry in ctx.entries:
            if entry.get("kind") != "skill_cast":
                continue
            actor_side = entry.get("actor_side", "")
            # Only track opponent skills
            side_val = actor_side
            if isinstance(side_val, str):
                is_mine = side_val == "我方"
            else:
                is_mine = 1 <= int(side_val) <= 6 if side_val is not None else False
            if is_mine:
                continue

            skill_name = entry.get("skill_name", "?")
            opp_active = ctx.state.get("opp_active") or {}
            pet_name = opp_active.get("name", "未知")

            if pet_name not in self._opp_skill_counts:
                self._opp_skill_counts[pet_name] = Counter()
            self._opp_skill_counts[pet_name][skill_name] += 1

            counts = self._opp_skill_counts[pet_name]
            total_uses = sum(counts.values())
            if total_uses >= 3:
                top_skill, top_count = counts.most_common(1)[0]
                if top_count >= 2 and total_uses >= 3:
                    ratio = top_count / total_uses
                    if ratio >= 0.5:
                        messages.append({
                            "type": "skill_preference",
                            "message": f"对手 {pet_name} 偏好使用 {top_skill} ({top_count}/{total_uses}次)",
                        })

        # Check for switch pattern
        if len(self._opp_switch_log) >= 2:
            low_hp_switches = sum(
                1 for s in self._opp_switch_log if s["prev_hp_pct"] < 0.4
            )
            if low_hp_switches >= 2:
                messages.append({
                    "type": "switch_pattern",
                    "message": "对手倾向在HP较低时换宠",
                })

        return messages
