"""场地状态投影测试。"""
from __future__ import annotations

from src.analysis.projection.field import project_weather_change


def test_project_weather_change_updates_weather_payload():
    state = {"weather": {"id": None}}

    project_weather_change(
        state,
        {"weather_id": 5, "weather_name": "雨天", "expire_round": 10},
    )

    assert state["weather"] == {
        "id": 5,
        "name": "雨天",
        "expire_round": 10,
    }

