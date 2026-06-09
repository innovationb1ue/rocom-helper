"""生命周期 opcode 格式化测试。"""
from __future__ import annotations

from src.analysis.formatting.lifecycle import (
    format_action_ack,
    format_battle_enter,
    format_battle_finish,
    format_round_flow,
    format_round_start,
    format_skill_declare,
    format_skill_select,
    format_special_refresh,
)


def test_format_battle_enter_splits_teams():
    event = format_battle_enter(
        {
            "battle_id": 1,
            "battle_mode": 22,
            "max_round": 50,
            "wrappers": [
                {"side": 1, "pet_name": "我方宠", "hp": 100, "max_hp": 100},
                {"side": 401, "pet_name": "敌方宠", "hp": 120, "max_hp": 120},
            ],
        },
        {},
    )

    assert event.kind == "battle_enter"
    assert event.detail["my_team"][0]["name"] == "我方宠"
    assert event.detail["opp_team"][0]["name"] == "敌方宠"


def test_format_round_start_preserves_status_contract():
    event = format_round_start(
        {"round": 2, "wrappers": [{"side": 1, "name": "我方宠", "hp": 90, "max_hp": 100, "energy": 8}]},
        {},
    )

    assert event.kind == "round_start"
    assert event.round == 2
    assert event.detail["pet_status"][0]["side"] == "我方"


def test_lifecycle_command_formatters_keep_summary_shapes():
    assert format_skill_select({"cmd_flag": 2}).summary == "我方选择: 换人"
    assert "服务端声明" in format_skill_declare({"actor_side": 401, "skill_name": "水流"}).summary
    assert "确认" in format_action_ack({"skill_name": "撞击", "current_hp": 10, "energy_after": 3}).summary
    assert "技能选项" in format_special_refresh({"skill_options": [{"skill_name": "A"}]}).summary
    assert format_round_flow({"round": 5}).round == 5


def test_format_battle_finish_uses_state_round():
    event = format_battle_finish({"result_name": "WIN", "rounds": 7, "seconds": 30}, {"round": 7})

    assert event.kind == "battle_finish"
    assert event.round == 7
    assert event.color == "green"
