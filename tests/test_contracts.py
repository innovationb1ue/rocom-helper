"""后端 WebSocket 消息契约回归测试。"""
from __future__ import annotations

from src.analysis.event_formatter import FormattedEvent
from src.analysis.models import ProcessResult
from src.analysis.replay_messages import build_battle_frame, build_battle_messages


def test_build_battle_messages_keeps_browser_contract_fields():
    result = ProcessResult(
        state={"battle_id": 1, "round": 3, "result": None},
        formatted_events=[
            FormattedEvent(
                kind="skill_cast",
                round=3,
                summary="测试事件",
                detail={"skill_id": 1001},
                icon="sword",
                color="blue",
            )
        ],
        battle_advice={
            "skill_analysis": [{"skill_id": 1001, "skill_name": "测试技能"}],
            "traits": [{"name": "我方特性"}],
            "opp_traits": [{"name": "对手特性"}],
            "opp_skill_analysis": [{"skill_id": 2002, "skill_name": "对手技能"}],
            "opp_skill_source": "used_skills",
        },
        hook_advice=[{"hook_id": "energy_monitor", "title": "能量"}],
        suggestions=[{"type": "info", "message": "建议"}],
        tactical={
            "actions": [],
            "opp_predicted": [],
            "round_number": 3,
            "confidence": "medium",
            "model_confidence": "high",
        },
    )

    messages = build_battle_messages(0x1324, result)
    by_type = {message["type"]: message for message in messages}

    assert by_type["battle_event"]["event"]["kind"] == "skill_cast"
    assert by_type["state_update"]["state"]["round"] == 3
    assert by_type["suggestions"]["suggestions"][0]["message"] == "建议"
    assert by_type["skill_analysis"]["skills"][0]["skill_id"] == 1001
    assert by_type["skill_analysis"]["opp_skill_source"] == "used_skills"
    assert by_type["hook_advice"]["advice"][0]["hook_id"] == "energy_monitor"
    assert by_type["tactical_recommendations"]["round_number"] == 3
    assert by_type["tactical_recommendations"]["model_confidence"] == "high"


def test_build_battle_messages_batches_multiple_formatted_events():
    result = ProcessResult(
        state={"battle_id": 1, "round": 4, "result": None},
        formatted_events=[
            FormattedEvent("damage", 4, "伤害 1", {"amount": 10}, "heart", "red"),
            FormattedEvent("heal", 4, "治疗 1", {"amount": 5}, "plus", "green"),
        ],
    )

    messages = build_battle_messages(0x1324, result)
    by_type = {message["type"]: message for message in messages}

    assert "battle_event" not in by_type
    assert by_type["battle_events"]["events"][0]["kind"] == "damage"
    assert by_type["battle_events"]["events"][1]["kind"] == "heal"
    assert by_type["state_update"]["state"]["round"] == 4


def test_build_battle_messages_emits_finish_summary_without_changing_state_contract():
    result = ProcessResult(
        state={
            "battle_id": 1,
            "round": 5,
            "result": "WIN",
            "my_pets": [],
            "opp_pets": [],
            "events": [],
        },
    )

    messages = build_battle_messages(0x132C, result)
    by_type = {message["type"]: message for message in messages}

    assert by_type["state_update"]["state"]["result"] == "WIN"
    assert by_type["battle_summary"]["summary"]["result"] == "WIN"
    assert by_type["battle_summary"]["summary"]["rounds"] == 5


def test_build_battle_frame_keeps_outputs_in_one_ordered_payload():
    result = ProcessResult(
        state={
            "battle_id": 1,
            "round": 6,
            "result": None,
            "my_active": {"battle_uid": "my-1"},
            "opp_active": {"battle_uid": "opp-1"},
        },
        formatted_events=[
            FormattedEvent("damage", 6, "造成伤害", {"amount": 40}, "heart", "red"),
        ],
        battle_advice={
            "skill_analysis": [{"skill_id": 1, "skill_name": "测试"}],
            "opp_skill_analysis": [{"skill_id": 2, "skill_name": "对手"}],
            "opp_skill_source": "used_skills",
        },
        hook_advice=[{"hook_id": "energy_monitor"}],
        suggestions=[{"type": "info", "message": "建议"}],
        tactical={
            "actions": [],
            "opp_predicted": [],
            "round_number": 6,
            "confidence": "medium",
            "model_confidence": "high",
        },
    )

    frame = build_battle_frame(0x1324, result, stream_id="stream-a", seq=3, event_index=2)

    assert frame["type"] == "battle_frame"
    assert frame["stream_id"] == "stream-a"
    assert frame["seq"] == 3
    assert frame["event_index"] == 2
    assert frame["round"] == 6
    assert frame["state"]["round"] == 6
    assert frame["events"][0]["kind"] == "damage"
    assert frame["skills"][0]["skill_id"] == 1
    assert frame["opp_skill_source"] == "used_skills"
    assert frame["hook_advice"][0]["hook_id"] == "energy_monitor"
    assert frame["tactical_recommendations"]["round_number"] == 6
    assert frame["tactical_recommendations"]["model_confidence"] == "high"
    assert frame["my_active_uid"] == "battle_uid:my-1"
    assert frame["opp_active_uid"] == "battle_uid:opp-1"
