"""processor_hook_flow 测试 — BattleProcessor hook 编排可独立验证。"""
from __future__ import annotations

from dataclasses import dataclass

from src.analysis.constants import (
    OPCODE_ACTION_RESOLVE,
    OPCODE_BATTLE_ENTER,
    OPCODE_BATTLE_FINISH,
    OPCODE_ROUND_START,
)
from src.analysis.hook_registry import HookAdvice, HookSignal, HookTrigger
from src.analysis.processor_hook_flow import (
    build_hook_context,
    opcode_to_triggers,
    run_hook_flow,
    serialize_hook_advice,
    write_hook_signals,
)


@dataclass
class FlowRegistry:
    signals: list | None = None

    def __post_init__(self):
        self.entered = []
        self.finished = []
        self.dispatched = []
        self.signals = self.signals or []

    def notify_battle_enter(self, ctx):
        self.entered.append(ctx.opcode)

    def notify_battle_finish(self, ctx):
        self.finished.append(ctx.opcode)

    def dispatch(self, trigger, ctx):
        self.dispatched.append((trigger, ctx.round_num, list(ctx.entries)))
        return [HookAdvice(hook_id="flow", priority=1, title=trigger.value)]

    def collect_signals(self, ctx):
        return self.signals


def test_build_hook_context_uses_state_round_and_detail_entries():
    ctx = build_hook_context(
        OPCODE_ACTION_RESOLVE,
        {"entries": [{"kind": "damage"}]},
        {"round": 6},
    )

    assert ctx.opcode == OPCODE_ACTION_RESOLVE
    assert ctx.round_num == 6
    assert ctx.entries == [{"kind": "damage"}]


def test_opcode_to_triggers_maps_lifecycle_and_action_entries():
    assert opcode_to_triggers(OPCODE_BATTLE_ENTER, {}) == [HookTrigger.ON_BATTLE_ENTER]
    assert opcode_to_triggers(OPCODE_ROUND_START, {}) == [HookTrigger.ON_ROUND_START]
    assert opcode_to_triggers(
        OPCODE_ACTION_RESOLVE,
        {"entries": [{"kind": "change_pet"}, {"kind": "defeat"}]},
    ) == [
        HookTrigger.ON_ACTION_RESOLVE,
        HookTrigger.ON_CHANGE_PET,
        HookTrigger.ON_DEFEAT,
    ]


def test_write_hook_signals_sets_and_clears_state_key():
    signal = HookSignal(hook_id="h", signal_type="avoid_skill", strength=0.7)
    state = {}

    write_hook_signals(state, [signal])
    assert state["_hook_signals"] == [signal.to_dict()]

    write_hook_signals(state, [])
    assert "_hook_signals" not in state


def test_serialize_hook_advice_preserves_public_dict_shape():
    advice = HookAdvice(
        hook_id="h",
        priority=1,
        title="提示",
        messages=[{"message": "ok"}],
    )

    assert serialize_hook_advice([advice]) == [advice.to_dict()]


def test_run_hook_flow_notifies_dispatches_writes_signals_and_serializes_advice():
    signal = HookSignal(
        hook_id="switch_advisor",
        signal_type="prefer_switch",
        target="替补",
        strength=0.8,
    )
    registry = FlowRegistry(signals=[signal])
    state = {"round": 3}

    advice = run_hook_flow(
        registry=registry,
        opcode=OPCODE_BATTLE_ENTER,
        detail={"entries": []},
        state=state,
    )

    assert registry.entered == [OPCODE_BATTLE_ENTER]
    assert registry.dispatched[0][0] == HookTrigger.ON_BATTLE_ENTER
    assert advice[0]["hook_id"] == "flow"
    assert state["_hook_signals"][0]["signal_type"] == "prefer_switch"


def test_run_hook_flow_notifies_finish_after_dispatch():
    registry = FlowRegistry()
    state = {"round": 9}

    run_hook_flow(
        registry=registry,
        opcode=OPCODE_BATTLE_FINISH,
        detail={},
        state=state,
    )

    assert registry.dispatched[0][0] == HookTrigger.ON_BATTLE_FINISH
    assert registry.finished == [OPCODE_BATTLE_FINISH]
