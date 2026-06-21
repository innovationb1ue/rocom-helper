"""战斗事件处理器 — 纯同步计算，不依赖 FastAPI/WebSocket。

BattleProcessor 从 BattleManager 中提取核心计算逻辑：
  - 状态追踪（BattleStateTracker）
  - 输出组装（processor_outputs）
  - 伤害预测（BattleAdvisor）
  - Hook 分析（HookRegistry）

BattleManager 和 BattleReplayRunner 都委托给此类，消除重复编排逻辑。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis import processor_analysis
from src.analysis import processor_event_flow
from src.analysis import processor_hooks
from src.analysis.battle_advisor import BattleAdvisor
from src.analysis.battle_summary import compute_battle_summary  # re-export for legacy imports
from src.analysis.battle_state import BattleStateTracker
from src.analysis.constants import (
    DAMAGE_OPCODES,
)
from src.analysis.hook_registry import HookRegistry, HookTrigger
from src.analysis.models import ProcessResult
from src.analysis.processor_policy import battle_is_active
from src.analysis.tactical_engine import TacticalEngine


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
        return processor_event_flow.process_battle_event(
            tracker=self.tracker,
            opcode=opcode,
            detail=detail,
            damage_opcodes=self._DAMAGE_OPCODES,
            include_analysis=self._include_analysis,
            include_hooks=self._include_hooks,
            include_formatting=self._include_formatting,
            advisor_provider=self._get_advisor,
            tactical_engine_provider=self._get_tactical_engine,
            hook_runner=self._run_hooks,
        )

    # ------------------------------------------------------------------
    # Damage analysis
    # ------------------------------------------------------------------

    def _get_advisor(self) -> BattleAdvisor:
        if self._advisor is None:
            self._advisor = BattleAdvisor()
        return self._advisor

    def _compute_damage_analysis(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return processor_analysis.compute_damage_analysis(state, advisor=self._get_advisor())

    @staticmethod
    def _has_usable_damage_predictions(advice: Optional[Dict[str, Any]]) -> bool:
        return processor_analysis.has_usable_damage_predictions(advice)

    # ------------------------------------------------------------------
    # Tactical recommendations
    # ------------------------------------------------------------------

    def _get_tactical_engine(self) -> TacticalEngine:
        if self._tactical_engine is None:
            self._tactical_engine = TacticalEngine()
        return self._tactical_engine

    def _compute_tactical(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return processor_analysis.compute_tactical(state, engine=self._get_tactical_engine())

    # ------------------------------------------------------------------
    # Hook dispatch
    # ------------------------------------------------------------------

    def _get_hook_registry(self) -> HookRegistry:
        if self._hook_registry is None:
            self._hook_registry = processor_hooks.create_default_hook_registry()
        return self._hook_registry

    def _run_hooks(
        self, opcode: int, detail: Dict[str, Any], state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return processor_hooks.run_hooks(
            registry=self._get_hook_registry(),
            opcode=opcode,
            detail=detail,
            state=state,
        )

    @staticmethod
    def opcode_to_triggers(opcode: int, detail: Dict[str, Any]) -> List[HookTrigger]:
        return processor_hooks.opcode_to_triggers(opcode, detail)

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
        return battle_is_active(state)
