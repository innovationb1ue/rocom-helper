"""BattleStateTracker 生命周期事件 helper 的直接单元测试。"""
from __future__ import annotations

from src.analysis.battle_state import BattleStateTracker
from src.analysis.state import lifecycle_events, weather


def test_weather_name_preserves_fallback_for_unknown_id():
    assert weather.weather_name("not-an-int", "未知天气") == "未知天气"


def test_handle_battle_enter_initializes_rosters_weather_and_side_bindings():
    tracker = BattleStateTracker()
    detail = {
        "battle_id": 123,
        "battle_mode": 22,
        "round": 0,
        "max_round": 50,
        "weather_id": 999999,
        "weather_expire_round": 7,
        "wrappers": [
            {
                "side": 1,
                "pet_id": 100,
                "slot": 1,
                "name": "我方宠",
                "hp": 300,
                "max_hp": 300,
                "battle_stats": [300, 1, 2, 3, 4, 188],
            },
            {
                "side": 401,
                "pet_id": 200,
                "slot": 401,
                "name": "敌方宠",
                "hp": 320,
                "max_hp": 320,
                "battle_stats": [320, 1, 2, 3, 4, 177],
            },
        ],
    }

    lifecycle_events.handle_battle_enter(tracker, detail)

    assert tracker.state["battle_id"] == 123
    assert tracker.state["phase"] == "selecting"
    assert tracker.state["weather"] == {
        "id": 999999,
        "name": None,
        "expire_round": 7,
        "changed_at_round": 0,
        "source": "battle_enter",
    }
    assert tracker.state["field_context"]["weather_history"][0]["id"] == 999999
    assert tracker.state["my_active"]["name"] == "我方宠"
    assert tracker.state["opp_active"]["name"] == "敌方宠"
    assert tracker._battle_side_pets[1] is tracker.state["my_active"]
    assert tracker._battle_side_pets[401] is tracker.state["opp_active"]


def test_round_start_and_action_ack_delegate_to_wrapper_sync():
    tracker = BattleStateTracker()
    lifecycle_events.handle_battle_enter(tracker, {
        "wrappers": [
            {"side": 1, "pet_id": 100, "slot": 1, "name": "我方宠", "hp": 300, "max_hp": 300},
        ],
    })

    lifecycle_events.handle_round_start(tracker, {
        "round": 3,
        "wrappers": [
            {"side": 1, "pet_id": 100, "slot": 1, "name": "我方宠", "hp": 280, "max_hp": 300},
        ],
    })

    assert tracker.state["round"] == 3
    assert tracker.state["phase"] == "resolving"
    assert tracker.state["my_active"]["current_hp"] == 280

    lifecycle_events.handle_action_ack(tracker, {
        "state_wrappers": [
            {"side": 1, "pet_id": 100, "slot": 1, "name": "我方宠", "hp": 260, "max_hp": 300},
        ],
    })

    assert tracker.state["my_active"]["current_hp"] == 260


def test_battle_finish_special_refresh_skill_declare_and_round_flow():
    tracker = BattleStateTracker()
    pet = {"pet_id": 100, "slot": 1, "side": 1, "name": "我方宠", "current_hp": 300, "max_hp": 300, "energy": 6}
    tracker.state["my_pets"] = [pet]
    tracker.state["my_active"] = pet
    tracker._bind_battle_side(1, pet, is_mine=True)

    lifecycle_events.handle_special_refresh(tracker, {"kind": "energy_bottle", "side": 1, "energy_delta": 5})
    assert pet["energy"] == 10

    lifecycle_events.handle_skill_declare(tracker, {"actor_side": 1, "skill_id": 7020370, "skill_name": "测试技能"})
    lifecycle_events.handle_skill_declare(tracker, {"actor_side": 1, "skill_id": 7020370, "skill_name": "测试技能"})
    assert pet["used_skills"] == [{"skill_id": 7020370, "skill_name": "测试技能"}]

    lifecycle_events.handle_round_flow(tracker, {"round": 8})
    assert tracker.state["round"] == 8

    lifecycle_events.handle_battle_finish(tracker, {
        "result_name": "WIN_HP",
        "finish_pet_infos": [{"pet_gid": 100, "remain_hp": 123}],
    })

    assert tracker.state["result"] == "WIN_HP"
    assert tracker.state["phase"] == "finished"
    assert pet["current_hp"] == 123
