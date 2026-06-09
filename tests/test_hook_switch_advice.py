"""switch_advice helper 测试 — 换宠建议纯逻辑可独立验证。"""
from __future__ import annotations

from src.analysis.constants import OPCODE_ACTION_RESOLVE, OPCODE_ROUND_START
from src.analysis.counter import CounterPicker
from src.analysis.hooks.switch_advice import (
    best_effectiveness,
    build_switch_messages,
    find_best_counter,
    is_opponent_switch,
    prefer_switch_target,
)
from src.game.type_chart import TypeChart


def _chart() -> TypeChart:
    return TypeChart()


def _counter_picker(chart: TypeChart) -> CounterPicker:
    return CounterPicker(chart)


def _my_pets():
    return [
        {"pet_id": 1, "name": "草龟", "types": [3], "current_hp": 200},
        {"pet_id": 2, "name": "水龟", "types": [2], "current_hp": 300},
        {"pet_id": 3, "name": "倒下精灵", "types": [2], "current_hp": 0},
    ]


def test_best_effectiveness_uses_strongest_attacking_type():
    assert best_effectiveness(_chart(), [3, 2], [1]) == 2.0


def test_is_opponent_switch_supports_numeric_and_text_sides():
    assert is_opponent_switch(OPCODE_ACTION_RESOLVE, [
        {"kind": "change_pet", "target_side": 401},
    ]) is True
    assert is_opponent_switch(OPCODE_ACTION_RESOLVE, [
        {"kind": "change_pet", "target_side": "对手"},
    ]) is True
    assert is_opponent_switch(OPCODE_ACTION_RESOLVE, [
        {"kind": "change_pet", "target_side": "我方"},
    ]) is False
    assert is_opponent_switch(OPCODE_ROUND_START, [
        {"kind": "change_pet", "target_side": 401},
    ]) is False


def test_find_best_counter_returns_original_living_pet():
    chart = _chart()
    opp_pet = {"pet_id": 101, "name": "火龙", "types": [1], "current_hp": 300}
    my_pets = _my_pets()

    best = find_best_counter(_counter_picker(chart), my_pets, opp_pet)

    assert best is my_pets[1]
    assert best["name"] == "水龟"


def test_build_switch_messages_for_bad_matchup():
    chart = _chart()
    messages = build_switch_messages(
        chart,
        _counter_picker(chart),
        {"pet_id": 1, "name": "草龟", "types": [3], "current_hp": 200},
        {"pet_id": 101, "name": "火龙", "types": [1], "current_hp": 300},
        _my_pets(),
        OPCODE_ROUND_START,
        [],
    )

    assert messages
    assert messages[0]["type"] == "bad_matchup"
    assert "水龟" in messages[0]["message"]


def test_build_switch_messages_for_opponent_switch_only_when_counter_is_different():
    chart = _chart()
    messages = build_switch_messages(
        chart,
        _counter_picker(chart),
        {"pet_id": 4, "name": "普通精灵", "types": [4], "current_hp": 200},
        {"pet_id": 101, "name": "火龙", "types": [1], "current_hp": 300},
        _my_pets(),
        OPCODE_ACTION_RESOLVE,
        [{"kind": "change_pet", "target_side": 401}],
    )

    assert messages
    assert messages[0]["type"] == "counter_switch"
    assert "水龟" in messages[0]["message"]


def test_prefer_switch_target_only_for_disadvantaged_matchup():
    chart = _chart()
    target = prefer_switch_target(
        chart,
        _counter_picker(chart),
        {"pet_id": 1, "name": "草龟", "types": [3], "current_hp": 200},
        {"pet_id": 101, "name": "火龙", "types": [1], "current_hp": 300},
        _my_pets(),
    )
    no_target = prefer_switch_target(
        chart,
        _counter_picker(chart),
        {"pet_id": 2, "name": "水龟", "types": [2], "current_hp": 300},
        {"pet_id": 101, "name": "火龙", "types": [1], "current_hp": 300},
        _my_pets(),
    )

    assert target is not None
    assert target["name"] == "水龟"
    assert no_target is None
