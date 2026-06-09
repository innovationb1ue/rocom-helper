"""物种/性格/进化/战斗配置/天气模块边界测试。"""
from __future__ import annotations

from src.data import species
from src.data.battle_config import get_battle_config, get_restraint_multipliers
from src.data.evolution import get_evolution_chain, get_evolution_pvp_mute_group
from src.data.nature import get_nature, get_nature_by_name, get_nature_stat_modifiers
from src.data.pet_species import (
    get_base_id_by_name,
    get_pet_implemented,
    get_pet_species,
    get_pet_species_stats,
    get_pet_species_types,
    get_pet_types_from_species,
    get_species_by_name,
)
from src.data.weather import get_weather, get_weather_by_name, get_weather_damage_mult


def test_pet_species_module_reads_species_and_name_index():
    pet = get_pet_species(3001)

    assert pet is not None
    assert pet["name"] == "喵喵"
    assert get_pet_species_stats(3001)["hp"] == 65
    assert get_pet_species_types(3001) == [3]
    assert get_pet_types_from_species(3001) == [3]
    assert get_pet_implemented(3001) is True
    assert get_base_id_by_name("喵喵") == 3001
    assert get_species_by_name("喵喵")["id"] == 3001


def test_nature_module_resolves_id_name_and_stat_modifiers():
    nature = get_nature(1)

    assert nature is not None
    assert nature["name"] == "大胆"
    assert get_nature_by_name("大胆")["id"] == 1
    assert get_nature_stat_modifiers(1) == {"atk": 0.1, "spa": -0.1}


def test_evolution_module_resolves_chain_and_pvp_mute_group():
    chain = get_evolution_chain(evolution_id=1)

    assert chain is not None
    assert chain["name"] == "水蓝蓝进化链"
    assert get_evolution_chain(petbase_id=3002)["id"] == 1
    assert get_evolution_pvp_mute_group(3002) == 1


def test_battle_config_module_resolves_restraint_defaults_from_data():
    cfg = get_battle_config()
    multipliers = get_restraint_multipliers()

    assert "restraint_percent" in cfg
    assert multipliers["single_super"] > 0
    assert multipliers["double_super"] >= multipliers["single_super"]


def test_weather_module_resolves_weather_and_damage_multiplier():
    weather = get_weather(1)

    assert weather is not None
    assert weather["name"] == "晴天"
    assert get_weather_by_name("晴天")["id"] == 1
    assert get_weather_damage_mult({"id": 1}, skill_element=1) == 1.5
    assert get_weather_damage_mult({"name": "雨天"}, skill_element=2) == 1.5
    assert get_weather_damage_mult({"name": "雨天"}, skill_element=1) == 1.0


def test_species_facade_keeps_compatibility_reexports():
    assert species.get_pet_species is get_pet_species
    assert species.get_nature is get_nature
    assert species.get_evolution_chain is get_evolution_chain
    assert species.get_battle_config is get_battle_config
    assert species.get_weather is get_weather
