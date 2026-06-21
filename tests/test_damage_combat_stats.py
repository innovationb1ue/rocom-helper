"""伤害属性解析模块测试。"""
from __future__ import annotations

import pytest

from src.analysis.damage import combat_stats
from src.analysis.damage.combat_stats import (
    get_pvp_template_stat,
    get_stat,
    get_stat_with_source,
    resolve_combat_stats,
)


def test_get_stat_with_source_prefers_total_value():
    pet = {"stats": [{"name": "ATK", "total": 250, "calc": 100, "bonus": 20}]}

    assert get_stat_with_source(pet, "ATK") == (250, "total")
    assert get_stat(pet, "ATK") == 250


def test_get_stat_with_source_falls_back_to_calc_bonus():
    pet = {"stats": [{"name": "SPA", "calc": 180, "bonus": 25}]}

    assert get_stat_with_source(pet, "SPA") == (205, "calc_bonus")


def test_get_pvp_template_stat_uses_species_and_nature_modifier():
    pet = {"base_id": 3001, "nature_stat_modifiers": {"atk": 0.1}}

    assert get_pvp_template_stat(pet, "ATK") == 159


def test_resolve_combat_stats_marks_protocol_estimates_as_medium_confidence():
    attacker = {
        "stats": [{"name": "ATK", "calc": 180, "bonus": 20}],
        "buffs": [],
    }
    defender = {
        "stats": [{"name": "DEF", "total": 100}],
        "buffs": [],
    }

    result = resolve_combat_stats(attacker, defender, damage_type=2)

    assert result is not None
    effective_atk, effective_def, ability_level, confidence, warnings, stat_sources = result
    assert effective_atk == 200
    assert effective_def == 100
    assert ability_level == 1.0
    assert confidence == "medium"
    assert "攻击属性来自 calc+bonus 估算" in warnings
    assert stat_sources == {
        "attack": "calc_bonus",
        "defense": "total",
        "attack_stat": "ATK",
        "defense_stat": "DEF",
    }


def test_resolve_combat_stats_applies_attack_and_defense_buffs(monkeypatch: pytest.MonkeyPatch):
    def fake_buff_modifiers(buff_list):
        marker = (buff_list or [{}])[0].get("marker")
        if marker == "attacker":
            return {"atk_up": 0.5}
        if marker == "defender":
            return {"def_down": 0.25}
        return {}

    monkeypatch.setattr(combat_stats, "get_buff_stat_modifiers", fake_buff_modifiers)
    attacker = {
        "stats": [{"name": "ATK", "total": 200}],
        "buffs": [{"marker": "attacker"}],
    }
    defender = {
        "stats": [{"name": "DEF", "total": 100}],
        "buffs": [{"marker": "defender"}],
    }

    result = resolve_combat_stats(attacker, defender, damage_type=2)

    assert result is not None
    effective_atk, effective_def, ability_level, confidence, warnings, _ = result
    assert effective_atk == 350
    assert effective_def == 100
    assert ability_level == 1.75
    assert confidence == "high"
    assert "能力等级 ×1.75" in warnings
