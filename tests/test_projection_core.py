"""状态投影共享工具测试。"""
from __future__ import annotations

from src.analysis.projection.core import active_for_side


def test_active_for_side_resolves_player_and_opponent_values():
    state = {
        "my_active": {"name": "我方"},
        "opp_active": {"name": "敌方"},
    }

    assert active_for_side(state, 1) == {"name": "我方"}
    assert active_for_side(state, "我方") == {"name": "我方"}
    assert active_for_side(state, 401) == {"name": "敌方"}
    assert active_for_side(state, "敌方") == {"name": "敌方"}
    assert active_for_side(state, None) is None

