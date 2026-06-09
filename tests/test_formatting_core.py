"""事件格式化共享工具测试。"""
from __future__ import annotations

from src.analysis.formatting.core import FormattedEvent, is_mine, resolve_pet_name, side_label


def test_formatted_event_to_dict_keeps_browser_fields():
    event = FormattedEvent(
        kind="damage",
        round=3,
        summary="敌方受到伤害",
        detail={"damage": 10},
        icon="thunderbolt",
        color="red",
    )

    assert event.to_dict() == {
        "kind": "damage",
        "round": 3,
        "summary": "敌方受到伤害",
        "detail": {"damage": 10},
        "icon": "thunderbolt",
        "color": "red",
    }


def test_side_helpers_keep_legacy_labels():
    assert side_label(0) == "系统"
    assert side_label(1) == "我方"
    assert side_label(401) == "敌方"
    assert side_label(None) == "?"
    assert is_mine(6) is True
    assert is_mine(401) is False
    assert is_mine("我方") is True


def test_resolve_pet_name_matches_slot_or_pet_id():
    state = {
        "my_pets": [{"slot": 1, "pet_id": 100, "name": "火龙"}],
        "opp_pets": [{"slot": 401, "pet_id": 200, "name": "水龟"}],
    }

    assert resolve_pet_name(1, True, state) == "火龙"
    assert resolve_pet_name(200, False, state) == "水龟"
    assert resolve_pet_name(999, True, state) == "999"
