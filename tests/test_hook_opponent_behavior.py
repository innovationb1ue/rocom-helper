"""opponent_behavior helper 测试 — 对手行为规则可独立验证。"""
from __future__ import annotations

from collections import Counter

from src.analysis.hooks.opponent_behavior import (
    append_switch_logs,
    build_behavior_data,
    build_behavior_messages,
    is_my_side,
    record_skill_casts,
    skill_preference_messages,
    switch_pattern_messages,
)


def _skill_cast(skill_name="火焰冲击", actor_side=401):
    return {
        "kind": "skill_cast",
        "skill_name": skill_name,
        "actor_side": actor_side,
    }


def _change_pet(new_name="水龙"):
    return {
        "kind": "change_pet",
        "new_pet_name": new_name,
    }


def test_is_my_side_keeps_legacy_side_rules():
    assert is_my_side(1) is True
    assert is_my_side(6) is True
    assert is_my_side(401) is False
    assert is_my_side("我方") is True
    assert is_my_side("对手") is False
    assert is_my_side("1") is False


def test_record_skill_casts_tracks_only_opponent_skills_by_active_pet():
    counts = {}

    record_skill_casts(
        [_skill_cast("火焰冲击"), _skill_cast("我方技能", actor_side=1)],
        {"name": "火龙"},
        counts,
    )

    assert counts["火龙"]["火焰冲击"] == 1
    assert "我方技能" not in counts["火龙"]


def test_skill_preference_messages_after_three_uses_with_majority():
    counts = {"火龙": Counter({"火焰冲击": 2, "火花": 1})}

    messages = skill_preference_messages(counts)

    assert messages
    assert messages[0]["type"] == "skill_preference"
    assert "火焰冲击" in messages[0]["message"]


def test_append_switch_logs_dedupes_by_round_and_new_pet():
    switch_log = []

    last_key = append_switch_logs(
        [_change_pet("水龙"), _change_pet("水龙")],
        switch_log,
        None,
        2,
        {"hp_pct": 0.333},
    )

    assert last_key == (2, "水龙")
    assert switch_log == [{"round": 2, "new_pet": "水龙", "prev_hp_pct": 0.33}]


def test_switch_pattern_messages_requires_two_low_hp_switches():
    assert switch_pattern_messages([
        {"prev_hp_pct": 0.2},
        {"prev_hp_pct": 0.3},
    ])[0]["type"] == "switch_pattern"
    assert switch_pattern_messages([
        {"prev_hp_pct": 0.2},
        {"prev_hp_pct": 0.8},
    ]) == []


def test_build_behavior_messages_updates_counts_and_uses_existing_switch_log():
    counts = {"火龙": Counter({"火焰冲击": 2})}
    switch_log = [
        {"round": 1, "new_pet": "a", "prev_hp_pct": 0.2},
        {"round": 2, "new_pet": "b", "prev_hp_pct": 0.3},
    ]

    messages = build_behavior_messages(
        [_skill_cast("火花")],
        {"name": "火龙"},
        counts,
        switch_log,
    )

    assert counts["火龙"]["火花"] == 1
    assert {message["type"] for message in messages} == {
        "skill_preference",
        "switch_pattern",
    }


def test_build_behavior_data_preserves_public_payload_shape():
    data = build_behavior_data(
        {"火龙": Counter({"火焰冲击": 2})},
        [{"round": 1, "new_pet": "水龙", "prev_hp_pct": 0.2}],
        3,
    )

    assert data == {
        "skill_history": {"火龙": {"火焰冲击": 2}},
        "switch_log": [{"round": 1, "new_pet": "水龙", "prev_hp_pct": 0.2}],
        "total_rounds": 3,
    }
