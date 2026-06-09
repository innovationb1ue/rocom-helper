"""HookRegistry 分发循环 — 独立于注册表状态，便于单元测试。"""
from __future__ import annotations

import logging
from typing import Any, List

logger = logging.getLogger(__name__)


def dispatch_hooks(
    hooks: List[Any],
    trigger: Any,
    ctx: Any,
) -> List[Any]:
    """按 trigger 分发 hook.process，单个 hook 失败不影响其他 hook。"""
    results: List[Any] = []
    for hook in hooks:
        if trigger not in hook.triggers:
            continue
        try:
            advice = hook.process(ctx)
            if advice is not None:
                results.append(advice)
        except Exception:
            logger.exception("Hook %s failed on %s", hook.hook_id, trigger.value)
    return results


def notify_hooks_enter(hooks: List[Any], ctx: Any) -> None:
    for hook in hooks:
        try:
            hook.on_battle_enter(ctx)
        except Exception:
            logger.exception("Hook %s on_battle_enter failed", hook.hook_id)


def notify_hooks_finish(hooks: List[Any], ctx: Any) -> None:
    for hook in hooks:
        try:
            hook.on_battle_finish(ctx)
        except Exception:
            logger.exception("Hook %s on_battle_finish failed", hook.hook_id)


def collect_hook_signals(hooks: List[Any], ctx: Any) -> List[Any]:
    """收集所有 hook signal，单个 hook 失败不影响其他 hook。"""
    signals: List[Any] = []
    for hook in hooks:
        try:
            signals.extend(hook.emit_signals(ctx))
        except Exception:
            logger.exception("Hook %s emit_signals failed", hook.hook_id)
    return signals


def reset_hooks(hooks: List[Any]) -> None:
    for hook in hooks:
        try:
            hook.reset()
        except Exception:
            logger.exception("Hook %s reset failed", hook.hook_id)
