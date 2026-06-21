"""BattleProcessor hook flow 纯编排 — context、trigger、signal 和 advice 输出。"""
from __future__ import annotations

from typing import Any, Dict, List, Protocol

from src.analysis.constants import (
    OPCODE_ACTION_RESOLVE,
    OPCODE_BATTLE_ENTER,
    OPCODE_BATTLE_FINISH,
    OPCODE_ROUND_START,
    OPCODE_SPECIAL_REFRESH,
)
from src.analysis.hook_registry import HookContext, HookTrigger


class HookRegistryLike(Protocol):
    def notify_battle_enter(self, ctx: HookContext) -> None: ...
    def notify_battle_finish(self, ctx: HookContext) -> None: ...
    def dispatch(self, trigger: HookTrigger, ctx: HookContext) -> List[Any]: ...
    def collect_signals(self, ctx: HookContext) -> List[Any]: ...


_OPCODE_TRIGGER_MAP: Dict[int, List[HookTrigger]] = {
    OPCODE_BATTLE_ENTER: [HookTrigger.ON_BATTLE_ENTER],
    OPCODE_ROUND_START: [HookTrigger.ON_ROUND_START],
    OPCODE_ACTION_RESOLVE: [HookTrigger.ON_ACTION_RESOLVE],
    OPCODE_SPECIAL_REFRESH: [HookTrigger.ON_SPECIAL_REFRESH],
    OPCODE_BATTLE_FINISH: [HookTrigger.ON_BATTLE_FINISH],
}


def build_hook_context(
    opcode: int,
    detail: Dict[str, Any],
    state: Dict[str, Any],
) -> HookContext:
    return HookContext(
        opcode=opcode,
        detail=detail,
        state=state,
        round_num=state.get("round", 0),
        entries=detail.get("entries", []),
    )


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


def write_hook_signals(state: Dict[str, Any], signals: List[Any]) -> None:
    if signals:
        state["_hook_signals"] = [signal.to_dict() for signal in signals]
    elif "_hook_signals" in state:
        del state["_hook_signals"]


def serialize_hook_advice(advice_items: List[Any]) -> List[Dict[str, Any]]:
    return [advice.to_dict() for advice in advice_items]


def run_hook_flow(
    *,
    registry: HookRegistryLike,
    opcode: int,
    detail: Dict[str, Any],
    state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    ctx = build_hook_context(opcode, detail, state)

    if opcode == OPCODE_BATTLE_ENTER:
        registry.notify_battle_enter(ctx)

    all_advice = []
    for trigger in opcode_to_triggers(opcode, detail):
        all_advice.extend(registry.dispatch(trigger, ctx))

    write_hook_signals(state, registry.collect_signals(ctx))

    if opcode == OPCODE_BATTLE_FINISH:
        registry.notify_battle_finish(ctx)

    return serialize_hook_advice(all_advice)
