"""伤害计算 4 阶段 hook 管线。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Literal

HookStage = Literal["pre_power", "post_base", "pre_final", "post_calc"]
DamageHook = Callable[[Dict[str, Any]], Dict[str, Any]]

HOOK_STAGES: tuple[HookStage, ...] = (
    "pre_power",
    "post_base",
    "pre_final",
    "post_calc",
)


class DamageHookPipeline:
    """管理并顺序执行伤害计算 hook。"""

    def __init__(self) -> None:
        self.hooks: Dict[HookStage, List[DamageHook]] = {
            stage: []
            for stage in HOOK_STAGES
        }

    def register(self, stage: HookStage, hook: DamageHook) -> None:
        if stage not in self.hooks:
            raise ValueError(f"Unknown hook stage: {stage}")
        self.hooks[stage].append(hook)

    def clear(self) -> None:
        for stage_hooks in self.hooks.values():
            stage_hooks.clear()

    def run(self, stage: HookStage, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if stage not in self.hooks:
            raise ValueError(f"Unknown hook stage: {stage}")
        for hook in self.hooks[stage]:
            ctx = hook(ctx)
        return ctx
