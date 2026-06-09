"""Sniffer lifecycle cleanup helpers."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

SetState = Callable[[str, str], None]
SetFlowCount = Callable[[int], None]
SetKeyHex = Callable[[Optional[str]], None]
OnFirstTraffic = Callable[[], None]


def stop_sniffer_instance(sniffer: Optional[Any], *, log: logging.Logger = logger) -> None:
    if sniffer is None:
        return
    try:
        if sniffer.is_running:
            sniffer.stop()
    except Exception as exc:
        log.warning("清理失败的 Sniffer 启动时出错: %s", exc)


def cleanup_failed_sniffer_start(
    *,
    runtime: Any,
    sniffer: Optional[Any],
    message: str,
    set_state: SetState,
    set_flow_count: SetFlowCount,
    log: logging.Logger = logger,
) -> None:
    runtime.cancel_tasks()
    stop_sniffer_instance(sniffer, log=log)
    set_flow_count(0)
    set_state("idle", message)


def stop_sniffer_runtime(
    *,
    runtime: Any,
    sniffer: Optional[Any],
    set_state: SetState,
    set_flow_count: SetFlowCount,
    set_key_hex: SetKeyHex,
    log: logging.Logger = logger,
) -> None:
    runtime.cancel_tasks()
    if sniffer is not None:
        try:
            sniffer.stop()
        except Exception as exc:
            log.warning("停止 Sniffer 时出错: %s", exc)
    set_flow_count(0)
    set_key_hex(None)
    set_state("idle", "已停止")


def packet_session_dir_from_sniffer(sniffer: Optional[Any]) -> Optional[Any]:
    if sniffer is None:
        return None
    pkt_logger = getattr(sniffer, "pkt_logger", None)
    if pkt_logger is None:
        return None
    return getattr(pkt_logger, "session_dir", None)


def monitor_sniffer_flow_tick(
    sniffer: Optional[Any],
    *,
    last_flow_count: int,
    on_first_traffic: OnFirstTraffic,
) -> int:
    if sniffer is None or not sniffer.is_running:
        return last_flow_count

    current_count = sniffer.flow_count
    for _ in range(max(0, current_count - last_flow_count)):
        on_first_traffic()
    return current_count
