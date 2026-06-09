"""BattleProcessor output helper tests."""
from __future__ import annotations

from src.analysis import processor_outputs
from src.analysis.formatting.core import FormattedEvent


def test_build_formatted_events_returns_empty_when_disabled():
    called = False

    def _formatter(*_args):
        nonlocal called
        called = True
        return []

    events = processor_outputs.build_formatted_events(
        include_formatting=False,
        opcode=1,
        detail={},
        state={},
        round_num=0,
        formatter=_formatter,
    )

    assert events == []
    assert called is False


def test_build_formatted_events_delegates_with_context_when_enabled():
    expected = [FormattedEvent(kind="info", round=2, summary="ok", detail={}, icon="i", color="blue")]
    calls = []

    def _formatter(opcode, detail, state, round_num):
        calls.append((opcode, detail, state, round_num))
        return expected

    events = processor_outputs.build_formatted_events(
        include_formatting=True,
        opcode=0x131A,
        detail={"kind": "round"},
        state={"round": 2},
        round_num=2,
        formatter=_formatter,
    )

    assert events is expected
    assert calls == [(0x131A, {"kind": "round"}, {"round": 2}, 2)]


def test_build_suggestions_delegates_to_injected_function():
    suggestions = processor_outputs.build_suggestions(
        {"round": 1},
        suggestions_fn=lambda state: [{"type": "info", "message": str(state["round"])}],
    )

    assert suggestions == [{"type": "info", "message": "1"}]


def test_build_process_result_preserves_contract_fields():
    event = FormattedEvent(kind="info", round=1, summary="ok", detail={}, icon="i", color="blue")
    result = processor_outputs.build_process_result(
        state={"round": 1},
        formatted_events=[event],
        battle_advice={"skill_analysis": []},
        hook_advice=[{"hook_id": "fake"}],
        suggestions=[{"type": "info", "message": "建议"}],
        tactical={"actions": []},
    )

    assert result.state == {"round": 1}
    assert result.formatted_events == [event]
    assert result.battle_advice == {"skill_analysis": []}
    assert result.hook_advice == [{"hook_id": "fake"}]
    assert result.suggestions == [{"type": "info", "message": "建议"}]
    assert result.tactical == {"actions": []}
