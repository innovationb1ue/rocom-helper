"""hook_dispatch 测试 — hook 分发循环脱离注册表独立验证。"""
from __future__ import annotations

from typing import List

from src.analysis.hook_dispatch import (
    collect_hook_signals,
    dispatch_hooks,
    notify_hooks_enter,
    notify_hooks_finish,
    reset_hooks,
)
from src.analysis.hook_registry import (
    AnalysisHook,
    HookAdvice,
    HookContext,
    HookSignal,
    HookTrigger,
)


class _DispatchHook(AnalysisHook):
    def __init__(
        self,
        hook_id: str,
        *,
        triggers: List[HookTrigger] = None,
        advice: HookAdvice = None,
        signal: HookSignal = None,
        fail_process: bool = False,
        fail_signal: bool = False,
    ) -> None:
        self._hook_id = hook_id
        self._triggers = triggers or [HookTrigger.ON_ROUND_START]
        self._advice = advice
        self._signal = signal
        self._fail_process = fail_process
        self._fail_signal = fail_signal
        self.enter_called = 0
        self.finish_called = 0
        self.reset_called = 0

    @property
    def hook_id(self) -> str:
        return self._hook_id

    @property
    def triggers(self) -> List[HookTrigger]:
        return self._triggers

    def process(self, ctx: HookContext):
        if self._fail_process:
            raise RuntimeError("process failed")
        return self._advice

    def on_battle_enter(self, ctx: HookContext) -> None:
        self.enter_called += 1

    def on_battle_finish(self, ctx: HookContext) -> None:
        self.finish_called += 1

    def reset(self) -> None:
        self.reset_called += 1

    def emit_signals(self, ctx: HookContext) -> List[HookSignal]:
        if self._fail_signal:
            raise RuntimeError("signal failed")
        return [self._signal] if self._signal else []


def _ctx() -> HookContext:
    return HookContext(opcode=0x131A, detail={}, state={"round": 1}, round_num=1)


def test_dispatch_hooks_filters_triggers_and_skips_none_advice():
    advice = HookAdvice(hook_id="ok", priority=1, title="提示")
    hooks = [
        _DispatchHook("ok", advice=advice),
        _DispatchHook("none"),
        _DispatchHook("other", triggers=[HookTrigger.ON_BATTLE_ENTER]),
    ]

    result = dispatch_hooks(hooks, HookTrigger.ON_ROUND_START, _ctx())

    assert result == [advice]


def test_dispatch_hooks_isolates_failing_hook():
    advice = HookAdvice(hook_id="ok", priority=1, title="提示")
    hooks = [
        _DispatchHook("fail", fail_process=True),
        _DispatchHook("ok", advice=advice),
    ]

    assert dispatch_hooks(hooks, HookTrigger.ON_ROUND_START, _ctx()) == [advice]


def test_lifecycle_helpers_call_every_hook():
    hooks = [_DispatchHook("a"), _DispatchHook("b")]
    ctx = _ctx()

    notify_hooks_enter(hooks, ctx)
    notify_hooks_finish(hooks, ctx)
    reset_hooks(hooks)

    assert [hook.enter_called for hook in hooks] == [1, 1]
    assert [hook.finish_called for hook in hooks] == [1, 1]
    assert [hook.reset_called for hook in hooks] == [1, 1]


def test_collect_hook_signals_isolates_failing_hook():
    signal = HookSignal(hook_id="ok", signal_type="avoid_skill", strength=0.8)
    hooks = [
        _DispatchHook("fail", fail_signal=True),
        _DispatchHook("ok", signal=signal),
    ]

    assert collect_hook_signals(hooks, _ctx()) == [signal]
