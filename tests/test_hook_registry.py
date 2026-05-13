"""HookRegistry 测试 — 注册、分发、生命周期、重置。"""
from __future__ import annotations

import pytest

from src.analysis.hook_registry import (
    AnalysisHook,
    HookAdvice,
    HookContext,
    HookRegistry,
    HookTrigger,
)


# ---------------------------------------------------------------------------
# Stub hooks
# ---------------------------------------------------------------------------


class _StubHook(AnalysisHook):
    def __init__(self, hid: str = "stub", triggers=None, advice=None):
        self._id = hid
        self._triggers = triggers or [HookTrigger.ON_ROUND_START]
        self._advice = advice
        self.enter_called = 0
        self.finish_called = 0
        self.reset_called = 0

    @property
    def hook_id(self) -> str:
        return self._id

    @property
    def triggers(self):
        return self._triggers

    def process(self, ctx: HookContext):
        return self._advice

    def on_battle_enter(self, ctx: HookContext) -> None:
        self.enter_called += 1

    def on_battle_finish(self, ctx: HookContext) -> None:
        self.finish_called += 1

    def reset(self) -> None:
        self.reset_called += 1


class _FailingHook(AnalysisHook):
    @property
    def hook_id(self) -> str:
        return "failing"

    @property
    def triggers(self):
        return [HookTrigger.ON_ROUND_START]

    def process(self, ctx: HookContext):
        raise RuntimeError("boom")


def _ctx(**overrides):
    defaults = {
        "opcode": 0x131A,
        "detail": {},
        "state": {"round": 1},
        "round_num": 1,
    }
    defaults.update(overrides)
    return HookContext(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_and_dispatch(self):
        reg = HookRegistry()
        advice = HookAdvice(hook_id="a", priority=2, title="t", messages=[])
        reg.register(_StubHook("a", advice=advice))
        result = reg.dispatch(HookTrigger.ON_ROUND_START, _ctx())
        assert len(result) == 1
        assert result[0].hook_id == "a"

    def test_duplicate_raises(self):
        reg = HookRegistry()
        reg.register(_StubHook("dup"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_StubHook("dup"))

    def test_empty_registry_dispatch(self):
        reg = HookRegistry()
        result = reg.dispatch(HookTrigger.ON_ROUND_START, _ctx())
        assert result == []

    def test_hook_ids(self):
        reg = HookRegistry()
        reg.register(_StubHook("x"))
        reg.register(_StubHook("y"))
        assert set(reg.hook_ids) == {"x", "y"}


class TestDispatch:
    def test_trigger_filtering(self):
        reg = HookRegistry()
        advice_a = HookAdvice(hook_id="a", priority=2, title="t", messages=[])
        reg.register(_StubHook("a", triggers=[HookTrigger.ON_ROUND_START], advice=advice_a))
        reg.register(_StubHook("b", triggers=[HookTrigger.ON_BATTLE_ENTER]))
        result = reg.dispatch(HookTrigger.ON_ROUND_START, _ctx())
        assert len(result) == 1
        assert result[0].hook_id == "a"

    def test_none_advice_skipped(self):
        reg = HookRegistry()
        reg.register(_StubHook("a", advice=None))
        result = reg.dispatch(HookTrigger.ON_ROUND_START, _ctx())
        assert result == []

    def test_failing_hook_doesnt_break_others(self):
        reg = HookRegistry()
        advice = HookAdvice(hook_id="ok", priority=1, title="t", messages=[])
        reg.register(_FailingHook())
        reg.register(_StubHook("ok", advice=advice))
        result = reg.dispatch(HookTrigger.ON_ROUND_START, _ctx())
        assert len(result) == 1
        assert result[0].hook_id == "ok"


class TestLifecycle:
    def test_notify_battle_enter(self):
        reg = HookRegistry()
        hook = _StubHook("a")
        reg.register(hook)
        reg.notify_battle_enter(_ctx())
        assert hook.enter_called == 1

    def test_notify_battle_finish(self):
        reg = HookRegistry()
        hook = _StubHook("a")
        reg.register(hook)
        reg.notify_battle_finish(_ctx())
        assert hook.finish_called == 1

    def test_reset(self):
        reg = HookRegistry()
        hook = _StubHook("a")
        reg.register(hook)
        reg.reset()
        assert hook.reset_called == 1

    def test_reset_on_all_hooks(self):
        reg = HookRegistry()
        a = _StubHook("a")
        b = _StubHook("b")
        reg.register(a)
        reg.register(b)
        reg.reset()
        assert a.reset_called == 1
        assert b.reset_called == 1


class TestHookAdvice:
    def test_to_dict(self):
        a = HookAdvice(
            hook_id="test",
            priority=1,
            title="测试",
            messages=[{"type": "info", "message": "hello"}],
            data={"key": "val"},
            expires_round=5,
        )
        d = a.to_dict()
        assert d["hook_id"] == "test"
        assert d["priority"] == 1
        assert d["messages"][0]["message"] == "hello"
        assert d["expires_round"] == 5
