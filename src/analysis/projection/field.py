"""场地 entry 状态投影。"""
from __future__ import annotations

from typing import Any, Dict


def project_weather_change(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    weather_id = entry.get("weather_id")
    if weather_id is not None:
        state["weather"] = {
            "id": weather_id,
            "name": entry.get("weather_name"),
            "expire_round": entry.get("expire_round"),
        }

