"""Action resolve 状态分发 helper 测试。"""
from __future__ import annotations

from src.analysis.state.action_resolve import handle_action_resolve


class FakeTracker:
    def __init__(self) -> None:
        self.perform_groups = []
        self.global_events = []
        self.damage_entries = []
        self.weather_entries = []
        self.sync_entries = []

    def _record_perform_group(self, entry):
        self.perform_groups.append(entry)

    def _record_global_event(self, kind, entry):
        self.global_events.append((kind, entry))

    def _handle_damage_entry(self, entry):
        self.damage_entries.append(entry)

    def _handle_weather_change_entry(self, entry):
        self.weather_entries.append(entry)

    def _apply_entry_sync_data(self, entry):
        self.sync_entries.append(entry)


def test_action_resolve_dispatches_entries_and_syncs_each_entry():
    tracker = FakeTracker()
    damage = {"kind": "damage", "damage": 88}
    weather = {"kind": "weather_change", "weather_id": 5}
    unknown = {"kind": "unknown_custom"}

    handle_action_resolve(tracker, {"entries": [damage, weather, unknown]})

    assert tracker.perform_groups == [damage, weather, unknown]
    assert tracker.global_events == [("weather_change", weather)]
    assert tracker.damage_entries == [damage]
    assert tracker.weather_entries == [weather]
    assert tracker.sync_entries == [damage, weather, unknown]
