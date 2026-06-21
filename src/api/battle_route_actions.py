"""Battle route action helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from src.api.battle_replay_endpoint import replay_battle_packets_payload
from src.api.battle_route_state import battle_effects_payload, battle_pets_payload


def battle_state_payload(manager: Any) -> dict:
    return manager.get_state()


def battle_pets_route_payload(manager: Any) -> dict:
    return battle_pets_payload(manager.get_state())


def battle_effects_route_payload(manager: Any) -> dict:
    return battle_effects_payload(manager.get_state())


async def replay_battle_route_payload(
    manager: Any,
    *,
    project_root: Path,
    session: str,
    delay_ms: int,
    stop_round: Optional[int],
) -> dict:
    return await replay_battle_packets_payload(
        manager=manager,
        project_root=project_root,
        session=session,
        delay_ms=delay_ms,
        stop_round=stop_round,
    )
