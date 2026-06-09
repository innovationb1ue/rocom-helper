"""BattleProcessor hook dispatch helper tests."""
from __future__ import annotations

from dataclasses import dataclass

from src.analysis import processor_hooks
from src.analysis.constants import (
    OPCODE_ACTION_RESOLVE,
    OPCODE_BATTLE_ENTER,
    OPCODE_BATTLE_FINISH,
    OPCODE_ROUND_START,
)
from src.analysis.hook_registry import HookAdvice, HookSignal, HookTrigger


@dataclass
class FakeRegistry:
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
        return [
            HookAdvice(
                hook_id="fake",
                priority=1,
                title=trigger.value,
                messages=[{"message": "ok"}],
            )
        ]

    def collect_signals(self, _ctx):
        return self.signals


def test_opcode_to_triggers_maps_lifecycle_and_action_entries():
    assert processor_hooks.opcode_to_triggers(OPCODE_BATTLE_ENTER, {}) == [HookTrigger.ON_BATTLE_ENTER]
    assert processor_hooks.opcode_to_triggers(OPCODE_ROUND_START, {}) == [HookTrigger.ON_ROUND_START]

    triggers = processor_hooks.opcode_to_triggers(
        OPCODE_ACTION_RESOLVE,
        {"entries": [{"kind": "change_pet"}, {"kind": "defeat"}]},
    )

    assert triggers == [
        HookTrigger.ON_ACTION_RESOLVE,
        HookTrigger.ON_CHANGE_PET,
        HookTrigger.ON_DEFEAT,
    ]


def test_run_hooks_notifies_lifecycle_dispatches_and_writes_signals():
    registry = FakeRegistry(signals=[
        HookSignal(
            hook_id="switch_advisor",
            signal_type="prefer_switch",
            target="替补",
            strength=0.8,
        )
    ])
    state = {"round": 3}

    advice = processor_hooks.run_hooks(
        registry=registry,
        opcode=OPCODE_BATTLE_ENTER,
        detail={"entries": []},
        state=state,
    )

    assert registry.entered == [OPCODE_BATTLE_ENTER]
    assert registry.dispatched[0][0] == HookTrigger.ON_BATTLE_ENTER
    assert advice[0]["hook_id"] == "fake"
    assert state["_hook_signals"][0]["signal_type"] == "prefer_switch"


def test_run_hooks_notifies_battle_finish_after_dispatch():
    registry = FakeRegistry()
    state = {"round": 9}

    processor_hooks.run_hooks(
        registry=registry,
        opcode=OPCODE_BATTLE_FINISH,
        detail={},
        state=state,
    )

    assert registry.dispatched[0][0] == HookTrigger.ON_BATTLE_FINISH
    assert registry.finished == [OPCODE_BATTLE_FINISH]


def test_run_hooks_clears_stale_signals_when_none_are_emitted():
    registry = FakeRegistry(signals=[])
    state = {"round": 1, "_hook_signals": [{"signal_type": "old"}]}

    processor_hooks.run_hooks(
        registry=registry,
        opcode=OPCODE_ROUND_START,
        detail={},
        state=state,
    )

    assert "_hook_signals" not in state


def test_create_default_hook_registry_registers_builtin_hooks():
    registry = processor_hooks.create_default_hook_registry()

    assert set(registry.hook_ids) == {
        "opponent_tracker",
        "switch_advisor",
        "energy_monitor",
    }
