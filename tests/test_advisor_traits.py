from __future__ import annotations

from src.analysis.advisor.traits import extract_traits


def test_extract_traits_reads_species_trait():
    traits = extract_traits({"name": "厉毒修萝"})

    assert traits[0]["name"] == "侵蚀"
    assert "中毒" in traits[0]["description"]


def test_extract_traits_deduplicates_species_and_buff_sources():
    traits = extract_traits({
        "name": "厉毒修萝",
        "buffs": [
            {"id": 2091009, "name": "侵蚀"},
            {"id": 2108015, "name": "仅精灵连击数+1"},
        ],
    })

    assert len(traits) == 1
    assert traits[0]["name"] == "侵蚀"


def test_extract_traits_keeps_known_innate_buff_and_ignores_unknown_buff():
    traits = extract_traits({
        "name": "未知宠物",
        "buffs": [{"id": 99999999}, {"id": 20410080}],
    })

    assert len(traits) == 1
    assert traits[0]["name"] == "临界防御"
    assert "生命值" in traits[0]["description"]
