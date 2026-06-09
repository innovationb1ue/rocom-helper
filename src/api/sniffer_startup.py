"""Sniffer 启动资源准备和线程启动 helper。"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Union

PathLike = Union[str, Path]


@dataclass(frozen=True)
class SnifferStartupResources:
    """一次 Sniffer 启动所需的外部资源。"""

    saved_key: Optional[bytes]
    packet_logger: Any

    @property
    def key_hex(self) -> Optional[str]:
        if self.saved_key is None:
            return None
        return self.saved_key.hex()


def monitor_session_id(
    *,
    strftime: Callable[[str], str] = time.strftime,
) -> str:
    return strftime("%Y-%m-%d_%H-%M-%S") + "_monitor"


def prepare_startup_resources(key_file: PathLike) -> SnifferStartupResources:
    """初始化抓包日志并加载持久化 key。"""
    from src.capture.crypto import load_key_from_file
    from src.capture.packet_logger import PacketLogger, setup_sniffer_logging

    setup_sniffer_logging()
    saved_key = load_key_from_file(str(key_file))
    return SnifferStartupResources(
        saved_key=saved_key,
        packet_logger=PacketLogger(session_id=monitor_session_id()),
    )


def create_sniffer(resources: SnifferStartupResources, *, on_event: Callable[[str, dict], None]) -> Any:
    """构造底层 Sniffer，延迟导入以便 API 层测试替换 capture 实现。"""
    from src.capture.sniffer import Sniffer

    return Sniffer(
        preset_key=resources.saved_key,
        on_event=on_event,
        packet_logger=resources.packet_logger,
    )


async def start_sniffer_threaded(sniffer: Any, *, timeout: float) -> None:
    """在线程中启动阻塞 Sniffer.start，并应用启动超时。"""
    await asyncio.wait_for(
        asyncio.to_thread(sniffer.start),
        timeout=timeout,
    )


async def wait_for_start_settle(delay: float = 0.3) -> None:
    await asyncio.sleep(delay)
