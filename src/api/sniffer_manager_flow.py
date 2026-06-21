"""SnifferManager 启动与状态评估 flow。

该模块只编排 manager 与底层 Sniffer/runtime 之间的生命周期步骤，
不依赖 FastAPI，也不持有全局单例。
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Optional, Union

from src.api.sniffer_lifecycle import cleanup_failed_sniffer_start
from src.api.sniffer_startup import (
    create_sniffer,
    prepare_startup_resources,
    start_sniffer_threaded,
    wait_for_start_settle,
)
from src.api.sniffer_state import evaluate_sniffer_status

PathLike = Union[str, Path]
GetSniffer = Callable[[], Optional[Any]]
SetSniffer = Callable[[Optional[Any]], None]
GetState = Callable[[], str]
GetKeyHex = Callable[[], Optional[str]]
SetKeyHex = Callable[[Optional[str]], None]
SetFlowCount = Callable[[int], None]
SetState = Callable[[str, str], None]
OnEvent = Callable[[str, dict], None]


async def evaluate_current_sniffer_state(
    *,
    sniffer: Optional[Any],
    current_state: str,
    key_hex: Optional[str],
    set_flow_count: SetFlowCount,
    set_state: SetState,
) -> None:
    """根据底层 sniffer status 推进 manager 状态。"""
    if sniffer is None or not sniffer.is_running:
        return

    evaluation = evaluate_sniffer_status(
        sniffer.get_status(),
        current_state=current_state,
        key_hex=key_hex,
    )
    set_flow_count(evaluation.flow_count)

    if evaluation.next_state is None or evaluation.next_message is None:
        return
    set_state(evaluation.next_state, evaluation.next_message)


def cleanup_failed_start_flow(
    *,
    runtime: Any,
    sniffer: Optional[Any],
    message: str,
    set_state: SetState,
    set_flow_count: SetFlowCount,
    set_sniffer: SetSniffer,
) -> None:
    """清理启动失败的 sniffer，并重置 manager 持有的 sniffer 引用。"""
    cleanup_failed_sniffer_start(
        runtime=runtime,
        sniffer=sniffer,
        message=message,
        set_state=set_state,
        set_flow_count=set_flow_count,
    )
    set_sniffer(None)


async def start_sniffer_manager_flow(
    *,
    get_sniffer: GetSniffer,
    set_sniffer: SetSniffer,
    runtime: Any,
    key_file: PathLike,
    start_timeout: float,
    get_state: GetState,
    get_key_hex: GetKeyHex,
    set_key_hex: SetKeyHex,
    set_flow_count: SetFlowCount,
    set_state: SetState,
    on_event: OnEvent,
    log: logging.Logger,
) -> None:
    """启动持久化 sniffer，保持 SnifferManager.start 的兼容语义。"""
    existing = get_sniffer()
    if existing is not None and existing.is_running:
        runtime.ensure_started()
        await evaluate_current_sniffer_state(
            sniffer=existing,
            current_state=get_state(),
            key_hex=get_key_hex(),
            set_flow_count=set_flow_count,
            set_state=set_state,
        )
        return

    resources = prepare_startup_resources(key_file)
    if resources.key_hex:
        set_key_hex(resources.key_hex)
        log.info("加载已保存密钥: %s", resources.key_hex)

    runtime.ensure_started()

    if resources.saved_key:
        set_state("listening", "监听中（已加载密钥）")
    else:
        set_state("listening", "监听中，等待游戏连接...")

    sniffer = create_sniffer(resources, on_event=on_event)
    set_sniffer(sniffer)
    try:
        await start_sniffer_threaded(sniffer, timeout=start_timeout)
    except asyncio.TimeoutError as exc:
        cleanup_failed_start_flow(
            runtime=runtime,
            sniffer=get_sniffer(),
            message="抓包启动超时，请确认已安装 Npcap 并尝试以管理员身份运行。",
            set_state=set_state,
            set_flow_count=set_flow_count,
            set_sniffer=set_sniffer,
        )
        raise RuntimeError("Sniffer start timed out") from exc
    except Exception as exc:
        cleanup_failed_start_flow(
            runtime=runtime,
            sniffer=get_sniffer(),
            message=f"抓包启动失败: {exc}",
            set_state=set_state,
            set_flow_count=set_flow_count,
            set_sniffer=set_sniffer,
        )
        raise

    await wait_for_start_settle()
    await evaluate_current_sniffer_state(
        sniffer=get_sniffer(),
        current_state=get_state(),
        key_hex=get_key_hex(),
        set_flow_count=set_flow_count,
        set_state=set_state,
    )

    log.info("持久化 Sniffer 已启动")
