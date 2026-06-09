"""Buff 修正展示测试。"""
from __future__ import annotations

from src.data import buff_modifiers
from src.data.buff_presentation import enrich_buff_modifiers, format_buff_modifier_summary


def test_format_buff_modifier_summary_orders_known_stats():
    assert format_buff_modifier_summary({"spa_down": 0.125, "atk_up": 0.1}) == [
        "物攻 +10%",
        "魔攻 -12.5%",
    ]


def test_enrich_buff_modifiers_adds_summary_without_mutating_input():
    raw = {"id": 20010020, "name": "魔攻等级提升", "stage": 2}

    enriched = enrich_buff_modifiers(raw)

    assert raw == {"id": 20010020, "name": "魔攻等级提升", "stage": 2}
    assert enriched["modifiers"] == {"spa_up": 0.2}
    assert enriched["modifier_summary"] == ["魔攻 +20%"]


def test_enrich_unknown_buff_keeps_original_fields():
    raw = {"id": 999999999, "name": "未知", "stage": 1}

    assert enrich_buff_modifiers(raw) == raw


def test_buff_modifiers_keeps_presentation_reexports():
    assert buff_modifiers.enrich_buff_modifiers is enrich_buff_modifiers
    assert buff_modifiers.format_buff_modifier_summary is format_buff_modifier_summary
