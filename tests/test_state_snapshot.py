"""Battle state snapshot projection tests."""
from __future__ import annotations

from src.analysis.state.snapshot import build_state_snapshot


def test_snapshot_filters_unhydrated_supply_placeholders_from_rosters():
    placeholder = {
        "name": "敌方",
        "current_hp": 0,
        "max_hp": 0,
        "supply_placeholder": True,
    }
    state = {
        "my_pets": [],
        "opp_pets": [
            {"name": "音速犬", "current_hp": 18, "max_hp": 366},
            placeholder,
        ],
        "my_active": None,
        "opp_active": placeholder,
    }

    snapshot = build_state_snapshot(state)

    assert [pet["name"] for pet in snapshot["opp_pets"]] == ["音速犬"]
    assert snapshot["opp_active"]["name"] == "敌方"
