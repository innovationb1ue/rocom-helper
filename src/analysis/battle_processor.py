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
from typing import Any, Dict, List, Optional

from src.analysis.battle_advisor import BattleAdvisor
from src.analysis.battle_summary import compute_battle_summary
from src.analysis.battle_state import BattleStateTracker
from src.analysis.constants import (
    DAMAGE_OPCODES,
    OPCODE_ACTION_RESOLVE,
    OPCODE_BATTLE_ENTER,
    OPCODE_BATTLE_FINISH,
    OPCODE_ROUND_START,
    OPCODE_SPECIAL_REFRESH,
)
from src.analysis.event_formatter import format_battle_event
from src.analysis.hook_registry import HookContext, HookRegistry, HookTrigger
from src.analysis.hooks import create_default_hooks
from src.analysis.models import ProcessResult
from src.analysis.prediction_reliability import build_prediction_reliability
from src.analysis.state_projector import project_state_after_entries
from src.analysis.suggestions import build_state_suggestions
from src.analysis.tactical_engine import TacticalEngine

logger = logging.getLogger(__name__)




# ---------------------------------------------------------------------------
# Opcode → HookTrigger 映射（唯一定义）
# ---------------------------------------------------------------------------
_OPCODE_TRIGGER_MAP: Dict[int, List[HookTrigger]] = {
    OPCODE_BATTLE_ENTER: [HookTrigger.ON_BATTLE_ENTER],
    OPCODE_ROUND_START: [HookTrigger.ON_ROUND_START],
    OPCODE_ACTION_RESOLVE: [HookTrigger.ON_ACTION_RESOLVE],
    OPCODE_SPECIAL_REFRESH: [HookTrigger.ON_SPECIAL_REFRESH],
    OPCODE_BATTLE_FINISH: [HookTrigger.ON_BATTLE_FINISH],
}


class BattleProcessor:
    """纯同步战斗事件处理器。持有 tracker/advisor/hooks，编排完整计算管线。"""

    _DAMAGE_OPCODES = DAMAGE_OPCODES

    def __init__(
        self,
        *,
        tracker: Optional[BattleStateTracker] = None,
        advisor: Optional[BattleAdvisor] = None,
        hook_registry: Optional[HookRegistry] = None,
        tactical_engine: Optional[TacticalEngine] = None,
        include_analysis: bool = True,
        include_hooks: bool = True,
        include_formatting: bool = True,
    ) -> None:
        self.tracker = tracker or BattleStateTracker()
        self._advisor = advisor
        self._hook_registry = hook_registry
        self._tactical_engine = tactical_engine
        self._include_analysis = include_analysis
        self._include_hooks = include_hooks
        self._include_formatting = include_formatting

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def process_event(self, opcode: int, detail: Dict[str, Any]) -> ProcessResult:
        """处理单个战斗事件，返回所有计算输出。"""
        needs_state_before = self._include_analysis and opcode == OPCODE_ACTION_RESOLVE
        state_before = self.tracker.get_state() if needs_state_before else None
        state = self.tracker.handle_event(opcode, detail)
        round_num = state.get("round", 0)
        battle_is_active = state.get("battle_id") is not None and state.get("result") is None

        # 1. 事件格式化
        formatted = []
        if self._include_formatting:
            formatted = format_battle_event(opcode, detail, state, round_num)

        # 2. 伤害预测
        battle_advice_dict: Optional[Dict[str, Any]] = None
        if self._include_analysis and battle_is_active and opcode in self._DAMAGE_OPCODES:
            if opcode == OPCODE_ACTION_RESOLVE:
                # 对 action_resolve 使用投影状态：buff/能量/换宠已生效但 HP 未扣减
                projected = project_state_after_entries(state_before or state, detail.get("entries", []))
                battle_advice_dict = self._compute_damage_analysis(projected)
                if not self._has_usable_damage_predictions(battle_advice_dict):
                    battle_advice_dict = self._compute_damage_analysis(state)
            else:
                battle_advice_dict = self._compute_damage_analysis(state)

        # 2.5 战术推荐
        tactical_dict: Optional[Dict[str, Any]] = None
        if self._include_analysis and battle_is_active and opcode in (OPCODE_ACTION_RESOLVE, OPCODE_ROUND_START):
            tactical_dict = self._compute_tactical(state)
            if tactical_dict is not None:
                tactical_dict["reliability"] = build_prediction_reliability(
                    state=state,
                    battle_advice=battle_advice_dict,
                    tactical=tactical_dict,
                )

        # 3. Hook 分析
        hook_advice_dicts: List[Dict[str, Any]] = []
        if self._include_hooks and battle_is_active:
            hook_advice_dicts = self._run_hooks(opcode, detail, state)

        # 4. 建议
        suggestions = build_state_suggestions(state)

        return ProcessResult(
            state=state,
            formatted_events=formatted,
            battle_advice=battle_advice_dict,
            hook_advice=hook_advice_dicts,
            suggestions=suggestions,
            tactical=tactical_dict,
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

    @staticmethod
    def _has_usable_damage_predictions(advice: Optional[Dict[str, Any]]) -> bool:
        if not advice:
            return False
        for skill in advice.get("skill_analysis", []):
            if skill.get("skill_damage_type") not in (2, 3):
                continue
            if skill.get("expected_damage") is not None:
                return True
        return False

    # ------------------------------------------------------------------
    # Tactical recommendations
    # ------------------------------------------------------------------

    def _get_tactical_engine(self) -> TacticalEngine:
        if self._tactical_engine is None:
            self._tactical_engine = TacticalEngine()
        return self._tactical_engine

    def _compute_tactical(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        engine = self._get_tactical_engine()
        rec = engine.recommend(state)
        if rec is None or not rec.actions:
            return None
        return rec.to_dict()

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

        if opcode == OPCODE_BATTLE_ENTER:
            registry.notify_battle_enter(ctx)

        triggers = self.opcode_to_triggers(opcode, detail)
        all_advice = []
        for trigger in triggers:
            all_advice.extend(registry.dispatch(trigger, ctx))

        # 收集 Hook 信号写入状态供 TacticalEngine 读取
        signals = registry.collect_signals(ctx)
        if signals:
            state["_hook_signals"] = [s.to_dict() for s in signals]
        elif "_hook_signals" in state:
            del state["_hook_signals"]

        if opcode == OPCODE_BATTLE_FINISH:
            registry.notify_battle_finish(ctx)

        return [a.to_dict() for a in all_advice]

    @staticmethod
    def opcode_to_triggers(opcode: int, detail: Dict[str, Any]) -> List[HookTrigger]:
        """opcode → HookTrigger 映射。0x1324 额外检查 entries 中的 kind。"""
        triggers = list(_OPCODE_TRIGGER_MAP.get(opcode, []))
        if opcode == OPCODE_ACTION_RESOLVE:
            kinds = {entry.get("kind") for entry in detail.get("entries", [])}
            if "change_pet" in kinds:
                triggers.append(HookTrigger.ON_CHANGE_PET)
            if "defeat" in kinds:
                triggers.append(HookTrigger.ON_DEFEAT)
        return triggers

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self.tracker = BattleStateTracker()
        self._advisor = None
        self._tactical_engine = None
        if self._hook_registry is not None:
            self._hook_registry.reset()

    def get_state(self) -> Dict[str, Any]:
        return self.tracker.get_state()

    def battle_active(self) -> bool:
        state = self.tracker.get_state()
        return state.get("battle_id") is not None and state.get("result") is None
