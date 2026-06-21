"""Battle replay endpoint helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from src.api.replay_service import replay_fixture_to_manager


def fixture_session_dir(project_root: Path, session: str) -> Path:
    return project_root / "tests" / "fixtures" / "packets" / session


async def replay_battle_packets_payload(
    *,
    manager: Any,
    project_root: Path,
    session: str,
    delay_ms: int,
    stop_round: Optional[int],
) -> dict:
    session_dir = fixture_session_dir(project_root, session)
    if not session_dir.is_dir():
        return {"status": "error", "message": f"Session not found: {session_dir}"}

    return await replay_fixture_to_manager(
        manager=manager,
        session_dir=session_dir,
        delay_ms=delay_ms,
        stop_round=stop_round,
    )
