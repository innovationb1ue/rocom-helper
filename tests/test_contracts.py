"""后端 WebSocket 消息契约回归测试。"""
from __future__ import annotations

from src.analysis.event_formatter import FormattedEvent
from src.analysis.models import ProcessResult
from src.analysis.replay_messages import build_battle_messages


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
