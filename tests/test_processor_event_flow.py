"""BattleProcessor single-event flow tests."""
from __future__ import annotations

from dataclasses import dataclass

from src.analysis import processor_event_flow
from src.analysis.constants import OPCODE_ACTION_RESOLVE, OPCODE_ROUND_START
from src.analysis.formatting.core import FormattedEvent


@dataclass
class FakeAdvice:
    skill_analysis: list

    def to_dict(self):
        return {"skill_analysis": self.skill_analysis}


class FakeAdvisor:
    def __init__(self):
        self.states = []

    def analyze(self, state):
        self.states.append(state)
        return FakeAdvice([{"skill_damage_type": 2, "expected_damage": 18}])


@dataclass
class FakeRecommendation:
    actions: list

    def to_dict(self):
        return {"actions": list(self.actions)}


class FakeTacticalEngine:
    def __init__(self):
        self.states = []

    def recommend(self, state):
        self.states.append(state)
        return FakeRecommendation([{"action_type": "skill"}])


class FakeTracker:
    def __init__(self, before=None, after=None):
        self.before = before or {"battle_id": 1, "round": 1, "result": None}
        self.after = after or {"battle_id": 1, "round": 2, "result": None}
        self.calls = []

    def get_state(self):
        self.calls.append("get_state")
        return self.before

    def handle_event(self, opcode, detail):
        self.calls.append(("handle_event", opcode, detail))
        return self.after


def _formatted_events_builder(**kwargs):
    if not kwargs["include_formatting"]:
        return []
    return [
        FormattedEvent(
            kind="info",
            round=kwargs["round_num"],
            summary="ok",
            detail={"opcode": kwargs["opcode"]},
            icon="i",
            color="blue",
        )
    ]


def test_process_battle_event_builds_full_outputs_when_active():
    tracker = FakeTracker()
    advisor = FakeAdvisor()
    tactical_engine = FakeTacticalEngine()
    hook_calls = []

    result = processor_event_flow.process_battle_event(
        tracker=tracker,
        opcode=OPCODE_ROUND_START,
        detail={"kind": "round"},
        damage_opcodes={OPCODE_ROUND_START},
        include_analysis=True,
        include_hooks=True,
        include_formatting=True,
        advisor_provider=lambda: advisor,
        tactical_engine_provider=lambda: tactical_engine,
        hook_runner=lambda opcode, detail, state: hook_calls.append((opcode, detail, state)) or [
            {"hook_id": "fake"}
        ],
        formatted_events_builder=_formatted_events_builder,
        suggestions_builder=lambda state: [{"type": "info", "message": str(state["round"])}],
    )

    assert result.state == tracker.after
    assert result.formatted_events[0].summary == "ok"
    assert result.battle_advice == {
        "skill_analysis": [{"skill_damage_type": 2, "expected_damage": 18}]
    }
    assert result.hook_advice == [{"hook_id": "fake"}]
    assert result.suggestions == [{"type": "info", "message": "2"}]
    assert result.tactical is not None
    assert result.tactical["actions"] == [{"action_type": "skill"}]
    assert "reliability" in result.tactical
    assert hook_calls == [(OPCODE_ROUND_START, {"kind": "round"}, tracker.after)]
    assert advisor.states == [tracker.after]
    assert tactical_engine.states == [tracker.after]


def test_process_battle_event_skips_optional_work_when_disabled():
    tracker = FakeTracker()
    calls = []

    result = processor_event_flow.process_battle_event(
        tracker=tracker,
        opcode=OPCODE_ROUND_START,
        detail={},
        damage_opcodes={OPCODE_ROUND_START},
        include_analysis=False,
        include_hooks=False,
        include_formatting=False,
        advisor_provider=lambda: calls.append("advisor"),
        tactical_engine_provider=lambda: calls.append("tactical"),
        hook_runner=lambda *_args: calls.append("hooks") or [],
        formatted_events_builder=_formatted_events_builder,
        suggestions_builder=lambda _state: [],
    )

    assert result.formatted_events == []
    assert result.battle_advice is None
    assert result.hook_advice == []
    assert result.tactical is None
    assert calls == []
    assert tracker.calls == [("handle_event", OPCODE_ROUND_START, {})]


def test_process_battle_event_snapshots_before_action_resolve_analysis():
    tracker = FakeTracker(
        before={"battle_id": 1, "round": 4, "result": None},
        after={"battle_id": 1, "round": 4, "result": None},
    )
    advisor = FakeAdvisor()

    processor_event_flow.process_battle_event(
        tracker=tracker,
        opcode=OPCODE_ACTION_RESOLVE,
        detail={"entries": []},
        damage_opcodes={OPCODE_ACTION_RESOLVE},
        include_analysis=True,
        include_hooks=False,
        include_formatting=False,
        advisor_provider=lambda: advisor,
        tactical_engine_provider=lambda: FakeTacticalEngine(),
        hook_runner=lambda *_args: [],
        formatted_events_builder=_formatted_events_builder,
        suggestions_builder=lambda _state: [],
    )

    assert tracker.calls == [
        "get_state",
        ("handle_event", OPCODE_ACTION_RESOLVE, {"entries": []}),
    ]
    assert advisor.states[0]["round"] == 4


def test_process_battle_event_skips_analysis_and_hooks_when_battle_inactive():
    tracker = FakeTracker(after={"battle_id": None, "round": 0, "result": None})
    calls = []

    result = processor_event_flow.process_battle_event(
        tracker=tracker,
        opcode=OPCODE_ROUND_START,
        detail={},
        damage_opcodes={OPCODE_ROUND_START},
        include_analysis=True,
        include_hooks=True,
        include_formatting=True,
        advisor_provider=lambda: calls.append("advisor"),
        tactical_engine_provider=lambda: calls.append("tactical"),
        hook_runner=lambda *_args: calls.append("hooks") or [],
        formatted_events_builder=_formatted_events_builder,
        suggestions_builder=lambda state: [{"type": "phase", "message": str(state["battle_id"])}],
    )

    assert result.battle_advice is None
    assert result.hook_advice == []
    assert result.tactical is None
    assert result.suggestions == [{"type": "phase", "message": "None"}]
    assert calls == []
