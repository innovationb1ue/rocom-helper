"""可扩展战斗分析钩子系统 — 注册、分发、生命周期管理。

基于 ABC 的钩子系统，用于实现可插拔的战斗分析模块。

核心类:
  - HookTrigger: 7 种触发时机枚举
  - HookContext: 传递给钩子的上下文（opcode, detail, state, round_num）
  - HookAdvice: 钩子输出的建议（hook_id, priority, title, messages）
  - AnalysisHook: 抽象基类，子类实现 hook_id, triggers, process()
  - HookRegistry: 注册表，管理钩子生命周期和事件分发

生命周期方法:
  - on_battle_enter(): 战斗开始时调用（用于初始化内部状态）
  - on_battle_finish(): 战斗结束时调用（用于清理）
  - reset(): 手动重置（用于回放场景）
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HookTrigger(Enum):
    ON_BATTLE_ENTER = "on_battle_enter"
    ON_ROUND_START = "on_round_start"
    ON_ACTION_RESOLVE = "on_action_resolve"
    ON_SPECIAL_REFRESH = "on_special_refresh"
    ON_BATTLE_FINISH = "on_battle_finish"
    ON_CHANGE_PET = "on_change_pet"
    ON_DEFEAT = "on_defeat"


@dataclass
class HookContext:
    opcode: int
    detail: Dict[str, Any]
    state: Dict[str, Any]
    round_num: int
    entries: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class HookAdvice:
    hook_id: str
    priority: int
    title: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    data: Optional[Dict[str, Any]] = None
    expires_round: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HookSignal:
    hook_id: str
    signal_type: str          # "avoid_skill" | "prefer_switch" | "priority_target"
    target: Optional[str] = None
    strength: float = 0.0     # 0.0-1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnalysisHook(ABC):

    @property
    @abstractmethod
    def hook_id(self) -> str: ...

    @property
    @abstractmethod
    def triggers(self) -> List[HookTrigger]: ...

    @abstractmethod
    def process(self, ctx: HookContext) -> Optional[HookAdvice]: ...

    def on_battle_enter(self, ctx: HookContext) -> None:
        pass

    def on_battle_finish(self, ctx: HookContext) -> None:
        pass

    def reset(self) -> None:
        pass

    def emit_signals(self, ctx: HookContext) -> List[HookSignal]:
        """可选：发出影响战术引擎评分的信号。"""
        return []


class HookRegistry:

    def __init__(self) -> None:
        self._hooks: Dict[str, AnalysisHook] = {}

    def register(self, hook: AnalysisHook) -> None:
        if hook.hook_id in self._hooks:
            raise ValueError(f"Hook '{hook.hook_id}' already registered")
        self._hooks[hook.hook_id] = hook

    def dispatch(self, trigger: HookTrigger, ctx: HookContext) -> List[HookAdvice]:
        results: List[HookAdvice] = []
        for hook in self._hooks.values():
            if trigger not in hook.triggers:
                continue
            try:
                advice = hook.process(ctx)
                if advice is not None:
                    results.append(advice)
            except Exception:
                logger.exception("Hook %s failed on %s", hook.hook_id, trigger.value)
        return results

    def notify_battle_enter(self, ctx: HookContext) -> None:
        for hook in self._hooks.values():
            try:
                hook.on_battle_enter(ctx)
            except Exception:
                logger.exception("Hook %s on_battle_enter failed", hook.hook_id)

    def notify_battle_finish(self, ctx: HookContext) -> None:
        for hook in self._hooks.values():
            try:
                hook.on_battle_finish(ctx)
            except Exception:
                logger.exception("Hook %s on_battle_finish failed", hook.hook_id)

    def collect_signals(self, ctx: HookContext) -> List[HookSignal]:
        """收集所有钩子发出的信号。"""
        signals: List[HookSignal] = []
        for hook in self._hooks.values():
            try:
                signals.extend(hook.emit_signals(ctx))
            except Exception:
                logger.exception("Hook %s emit_signals failed", hook.hook_id)
        return signals

    def reset(self) -> None:
        for hook in self._hooks.values():
            try:
                hook.reset()
            except Exception:
                logger.exception("Hook %s reset failed", hook.hook_id)

    @property
    def hook_ids(self) -> List[str]:
        return list(self._hooks.keys())
