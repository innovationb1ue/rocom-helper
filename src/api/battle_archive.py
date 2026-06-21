"""Battle report auto-archive helpers."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from src.analysis.battle_report import archive_latest_completed_battle
from src.analysis.constants import OPCODE_BATTLE_FINISH

logger = logging.getLogger(__name__)

ArchiveFunction = Callable[[Path], Any]
SessionDirProvider = Callable[[], Optional[Path]]
ArchiveCoroutineFactory = Callable[[], Awaitable[Optional[Any]]]


def should_archive_completed_battle(opcode: int, *, enable_archive: bool) -> bool:
    return enable_archive and opcode == OPCODE_BATTLE_FINISH


def packet_session_dir_from_sniffer() -> Optional[Path]:
    from src.api.sniffer_manager import get_sniffer_manager

    return get_sniffer_manager().get_packet_session_dir()


async def archive_completed_battle(
    *,
    session_dir_provider: SessionDirProvider = packet_session_dir_from_sniffer,
    archive_fn: ArchiveFunction = archive_latest_completed_battle,
    log: logging.Logger = logger,
) -> Optional[Any]:
    session_dir = session_dir_provider()
    if session_dir is None:
        return None
    try:
        archive_path = await asyncio.to_thread(archive_fn, session_dir)
    except Exception:
        log.exception("自动归档战斗报告失败")
        return None
    if archive_path is not None:
        log.info("战斗报告已自动归档: %s", archive_path)
    return archive_path


def schedule_completed_battle_archive(
    opcode: int,
    *,
    enable_archive: bool,
    archive_coro_factory: ArchiveCoroutineFactory = archive_completed_battle,
) -> Optional[asyncio.Task[Optional[Any]]]:
    if not should_archive_completed_battle(opcode, enable_archive=enable_archive):
        return None
    return asyncio.create_task(archive_coro_factory())
