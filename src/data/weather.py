"""天气数据和天气伤害倍率查询。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.data.catalog import DATA_DIR, _read_json_dict

_WATER_TYPE_ID = 2  # type_chart.json 中水的 ID
_weather_cache: Optional[Dict[str, Any]] = None


def _load_weather_map() -> Dict[str, Any]:
    global _weather_cache
    if _weather_cache is not None:
        return _weather_cache
    path = DATA_DIR / "weather_map.json"
    _weather_cache = _read_json_dict(path)
    return _weather_cache


def get_weather(weather_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """按 weather_id 查找天气数据。"""
    if weather_id is None:
        return None
    return _load_weather_map().get(str(weather_id))


def get_weather_by_name(name: str) -> Optional[Dict[str, Any]]:
    """按天气名称查找天气数据。"""
    for value in _load_weather_map().values():
        if value.get("name") == name:
            return value
    return None


def get_weather_damage_mult(weather: Optional[Dict[str, Any]], skill_element: int) -> float:
    """根据天气和技能属性返回伤害修正倍率。"""
    if not weather:
        return 1.0

    weather_id = weather.get("weather") or weather.get("id")
    wdata = get_weather(weather_id)
    if wdata:
        wname = wdata.get("name", "")
        if "雨" in wname and skill_element == _WATER_TYPE_ID:
            return 1.5
        if "晴" in wname:
            _FIRE_TYPE_ID = 1
            if skill_element == _FIRE_TYPE_ID:
                return 1.5
        return 1.0

    name = weather.get("name") or ""
    if not isinstance(name, str):
        name = ""
    is_rain = "雨" in name
    if is_rain and skill_element == _WATER_TYPE_ID:
        return 1.5
    return 1.0


def reset_weather_caches() -> None:
    global _weather_cache
    _weather_cache = None
