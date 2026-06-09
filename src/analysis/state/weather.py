"""Weather helpers for BattleStateTracker."""
from __future__ import annotations

from typing import Any, Dict


def weather_name(weather_id: Any, fallback: Any = None) -> Any:
    """Resolve a weather id to a display name, preserving caller fallback."""
    if weather_id is not None:
        try:
            from src.data.loader import get_weather
            weather = get_weather(int(weather_id))
        except (TypeError, ValueError):
            weather = None
        if isinstance(weather, dict) and weather.get("name"):
            return weather["name"]
    return fallback


def set_weather_current(tracker: Any, weather: Dict[str, Any]) -> None:
    """Update both top-level weather and field-context current weather."""
    tracker.state["weather"] = weather
    tracker._field_context()["weather_current"] = weather
