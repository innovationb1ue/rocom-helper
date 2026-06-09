"""BattleProcessor 的 hook 生命周期与分发 helpers。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.analysis.hook_registry import HookRegistry, HookTrigger
from src.analysis.hooks import create_default_hooks
from src.analysis.processor_hook_flow import HookRegistryLike
from src.analysis import processor_hook_flow


def create_default_hook_registry() -> HookRegistry:
    registry = HookRegistry()
    for hook in create_default_hooks():
        registry.register(hook)
    return registry


def opcode_to_triggers(opcode: int, detail: Dict[str, Any]) -> List[HookTrigger]:
    return processor_hook_flow.opcode_to_triggers(opcode, detail)


def write_hook_signals(state: Dict[str, Any], signals: List[Any]) -> None:
    processor_hook_flow.write_hook_signals(state, signals)


def run_hooks(
    *,
    registry: HookRegistryLike,
    opcode: int,
    detail: Dict[str, Any],
    state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return processor_hook_flow.run_hook_flow(
        registry=registry,
        opcode=opcode,
        detail=detail,
        state=state,
    )
