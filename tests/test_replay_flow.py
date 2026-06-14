"""Replay runner helper tests."""
from __future__ import annotations

from src.analysis.formatting.core import FormattedEvent
from src.analysis.models import ProcessResult
from src.analysis.replay_flow import (
    filter_process_result,
    make_event_snapshot,
    should_stop_before_event,
    should_stop_replay,
    update_round_snapshot,
)
from src.analysis.replay_models import RoundSnapshot


def test_filter_process_result_applies_output_flags_and_copies_payloads():
    event = FormattedEvent(
        kind="damage",
        round=2,
        summary="造成伤害",
        detail={"amount": 10},
        icon="sword",
        color="red",
    )
    result = ProcessResult(
        state={"round": 2},
        formatted_events=[event],
        battle_advice={"skill_analysis": [{"skill_name": "测试"}]},
        hook_advice=[{"hook_id": "energy_monitor"}],
        suggestions=[{"type": "info", "message": "提示"}],
        tactical={"actions": [{"score": 1}]},
    )

    filtered, formatted, battle_advice, hook_advice, suggestions = filter_process_result(
        result,
        include_analysis=False,
        include_hooks=False,
        include_formatting=True,
    )

    assert filtered.state is result.state
    assert filtered.formatted_events == [event]
    assert filtered.battle_advice is None
    assert filtered.hook_advice == []
    assert filtered.tactical is None
    assert formatted == [event.to_dict()]
    assert battle_advice is None
    assert hook_advice == []
    assert suggestions == result.suggestions
    assert suggestions is not result.suggestions


def test_update_round_snapshot_aggregates_event_outputs_and_analysis():
    round_map: dict[int, RoundSnapshot] = {}
    event = make_event_snapshot(
        index=0,
        opcode=0x1324,
        kind="action_resolve",
        round_num=3,
        state_before={"round": 2},
        state_after={"round": 3},
        formatted_events=[{"kind": "damage"}],
        battle_advice={"skill_analysis": [{"skill_name": "测试技能"}]},
        hook_advice=[],
        suggestions=[{"type": "info", "message": "提示"}],
        tactical={"actions": [{"score": 1}]},
        messages=[{"type": "state_update"}],
    )

    snapshot = update_round_snapshot(
        round_map,
        round_num=3,
        state_before=event.state_before,
        state_after=event.state_after,
        event=event,
        battle_advice={
            "skill_analysis": [{"skill_name": "测试技能"}],
            "traits": [{"name": "特性"}],
            "opp_traits": [{"name": "对手特性"}],
            "opp_skill_analysis": [{"skill_name": "对手技能"}],
            "opp_skill_source": "used",
        },
        formatted_events=event.formatted_events,
        suggestions=event.suggestions,
        messages=event.messages,
        tactical=event.tactical,
    )

    assert round_map[3] is snapshot
    assert snapshot.events == [event]
    assert snapshot.state_at_start == {"round": 2}
    assert snapshot.state_at_end == {"round": 3}
    assert snapshot.damage_predictions == [{"skill_name": "测试技能"}]
    assert snapshot.traits == [{"name": "特性"}]
    assert snapshot.opp_traits == [{"name": "对手特性"}]
    assert snapshot.opp_skill_analysis == [{"skill_name": "对手技能"}]
    assert snapshot.opp_skill_source == "used"
    assert snapshot.suggestions == [{"type": "info", "message": "提示"}]
    assert snapshot.tactical_recommendations == {"actions": [{"score": 1}]}

    update_round_snapshot(
        round_map,
        round_num=3,
        state_before=event.state_before,
        state_after={"round": 3, "phase": "resolving"},
        event=event,
        battle_advice=None,
        formatted_events=[],
        suggestions=[],
        messages=[],
        tactical=None,
    )

    assert snapshot.suggestions == []


def test_should_stop_replay_only_stops_on_round_boundary_events():
    assert should_stop_replay(5, 5, 0x1324) is False
    assert should_stop_replay(5, 6, 0x131A) is True
    assert should_stop_replay(5, 5, 0x130C) is False
    assert should_stop_replay(None, 5, 0x1324) is False


def test_should_stop_before_event_stops_only_before_next_round_start():
    assert should_stop_before_event(5, {"round": 5}, 0x131A, {"round": 6}) is True
    assert should_stop_before_event(5, {"round": 5}, 0x131A, {"round": 5}) is False
    assert should_stop_before_event(5, {"round": 5}, 0x132C, {}) is False
