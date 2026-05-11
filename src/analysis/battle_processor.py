"""战斗事件处理器 — 纯同步计算，不依赖 FastAPI/WebSocket。

BattleProcessor 从 BattleManager 中提取核心计算逻辑：
  - 状态追踪（BattleStateTracker）
  - 事件格式化（format_battle_event）
  - 伤害预测（BattleAdvisor）
  - Hook 分析（HookRegistry）

BattleManager 和 BattleReplayRunner 都委托给此类，消除重复编排逻辑。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.analysis.battle_advisor import BattleAdvisor
from src.analysis.battle_state import BattleStateTracker
from src.analysis.event_formatter import format_battle_event, FormattedEvent
from src.analysis.hook_registry import HookContext, HookRegistry, HookTrigger
from src.analysis.hooks import create_default_hooks

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """process_event 的返回值 — 单个事件的所有计算输出。"""
    state: Dict[str, Any]
    formatted_events: List[FormattedEvent] = field(default_factory=list)
    battle_advice: Optional[Dict[str, Any]] = None
    hook_advice: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Opcode → HookTrigger 映射（唯一定义）
# ---------------------------------------------------------------------------
_OPCODE_TRIGGER_MAP: Dict[int, List[HookTrigger]] = {
    0x1316: [HookTrigger.ON_BATTLE_ENTER],
    0x131A: [HookTrigger.ON_ROUND_START],
    0x1324: [HookTrigger.ON_ACTION_RESOLVE],
    0x13F4: [HookTrigger.ON_SPECIAL_REFRESH],
    0x132C: [HookTrigger.ON_BATTLE_FINISH],
}


class BattleProcessor:
    """纯同步战斗事件处理器。持有 tracker/advisor/hooks，编排完整计算管线。"""

    _DAMAGE_OPCODES = {0x1316, 0x131A, 0x1324, 0x13F4}

    def __init__(self) -> None:
        self.tracker = BattleStateTracker()
        self._advisor: Optional[BattleAdvisor] = None
        self._hook_registry: Optional[HookRegistry] = None

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def process_event(self, opcode: int, detail: Dict[str, Any]) -> ProcessResult:
        """处理单个战斗事件，返回所有计算输出。"""
        state = self.tracker.handle_event(opcode, detail)
        round_num = state.get("round", 0)

        # 1. 事件格式化
        formatted = format_battle_event(opcode, detail, state, round_num)

        # 2. 伤害预测
        battle_advice_dict: Optional[Dict[str, Any]] = None
        if self.battle_active() and opcode in self._DAMAGE_OPCODES:
            battle_advice_dict = self._compute_damage_analysis(state)

        # 3. Hook 分析
        hook_advice_dicts: List[Dict[str, Any]] = []
        if self.battle_active():
            hook_advice_dicts = self._run_hooks(opcode, detail, state)

        # 4. 建议
        suggestions = self.tracker.get_suggestions()

        return ProcessResult(
            state=state,
            formatted_events=formatted,
            battle_advice=battle_advice_dict,
            hook_advice=hook_advice_dicts,
            suggestions=suggestions,
        )

    # ------------------------------------------------------------------
    # Damage analysis
    # ------------------------------------------------------------------

    def _get_advisor(self) -> BattleAdvisor:
        if self._advisor is None:
            self._advisor = BattleAdvisor()
        return self._advisor

    def _compute_damage_analysis(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        advisor = self._get_advisor()
        advice = advisor.analyze(state)
        if not advice.skill_analysis:
            return None
        return advice.to_dict()

    # ------------------------------------------------------------------
    # Hook dispatch
    # ------------------------------------------------------------------

    def _get_hook_registry(self) -> HookRegistry:
        if self._hook_registry is None:
            self._hook_registry = HookRegistry()
            for hook in create_default_hooks():
                self._hook_registry.register(hook)
        return self._hook_registry

    def _run_hooks(
        self, opcode: int, detail: Dict[str, Any], state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        registry = self._get_hook_registry()
        ctx = HookContext(
            opcode=opcode,
            detail=detail,
            state=state,
            round_num=state.get("round", 0),
            entries=detail.get("entries", []),
        )

        if opcode == 0x1316:
            registry.notify_battle_enter(ctx)

        triggers = self.opcode_to_triggers(opcode, detail)
        all_advice = []
        for trigger in triggers:
            all_advice.extend(registry.dispatch(trigger, ctx))

        if opcode == 0x132C:
            registry.notify_battle_finish(ctx)

        return [a.to_dict() for a in all_advice]

    @staticmethod
    def opcode_to_triggers(opcode: int, detail: Dict[str, Any]) -> List[HookTrigger]:
        """opcode → HookTrigger 映射。0x1324 额外检查 entries 中的 kind。"""
        triggers = list(_OPCODE_TRIGGER_MAP.get(opcode, []))
        if opcode == 0x1324:
            for entry in detail.get("entries", []):
                kind = entry.get("kind")
                if kind == "change_pet":
                    triggers.append(HookTrigger.ON_CHANGE_PET)
                elif kind == "defeat":
                    triggers.append(HookTrigger.ON_DEFEAT)
        return triggers

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self.tracker = BattleStateTracker()
        self._advisor = None
        if self._hook_registry is not None:
            self._hook_registry.reset()

    def get_state(self) -> Dict[str, Any]:
        return self.tracker.get_state()

    def battle_active(self) -> bool:
        state = self.tracker.get_state()
        return state.get("battle_id") is not None and state.get("result") is None
