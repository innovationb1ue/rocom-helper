"""格式化事件合并测试。"""
from __future__ import annotations

from src.analysis.formatting.core import FormattedEvent
from src.analysis.formatting.merge import merge_damage_events


def _damage(*, hp_after: int, ledger_id: int) -> FormattedEvent:
    return FormattedEvent(
        kind="damage",
        round=4,
        summary="敌方 受到 10 伤害",
        detail={
            "target_side": "敌方",
            "damage": 10,
            "hp_after": hp_after,
            "skill_name": "连击",
            "ledger_id": ledger_id,
        },
        icon="thunderbolt",
        color="red",
    )


def _named_damage(*, hp_after: int, ledger_id: int) -> FormattedEvent:
    event = _damage(hp_after=hp_after, ledger_id=ledger_id)
    event.detail["target_name"] = "熔岩布丁"
    return event


def test_merge_damage_events_merges_consecutive_identical_hits():
    merged = merge_damage_events([_damage(hp_after=90, ledger_id=1), _damage(hp_after=80, ledger_id=2)])

    assert len(merged) == 1
    assert merged[0].detail["hit_count"] == 2
    assert merged[0].detail["hp_after"] == 80
    assert merged[0].detail["ledger_ids"] == [1, 2]
    assert "10x2" in merged[0].summary


def test_merge_damage_events_keeps_side_and_pet_name_in_summary():
    merged = merge_damage_events([
        _named_damage(hp_after=90, ledger_id=1),
        _named_damage(hp_after=80, ledger_id=2),
    ])

    assert merged[0].summary == "敌方(熔岩布丁) 受到 10x2 伤害 (HP→80) [连击]"


def test_merge_damage_events_keeps_non_matching_events_separate():
    other = FormattedEvent("heal", 4, "治疗", {}, "heart", "green")

    merged = merge_damage_events([_damage(hp_after=90, ledger_id=1), other, _damage(hp_after=80, ledger_id=2)])

    assert [event.kind for event in merged] == ["damage", "heal", "damage"]
