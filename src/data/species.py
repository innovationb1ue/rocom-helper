"""宠物物种、性格、进化链、战斗配置和天气数据兼容门面。"""
from __future__ import annotations

from src.data.battle_config import (
    get_battle_config,
    get_restraint_multipliers,
    reset_battle_config_caches,
)
from src.data.evolution import (
    get_evolution_chain,
    get_evolution_pvp_mute_group,
    reset_evolution_caches,
)
from src.data.nature import (
    get_nature,
    get_nature_by_name,
    get_nature_stat_modifiers,
    reset_nature_caches,
)
from src.data.pet_species import (
    _load_pet_species,
    get_base_id_by_name,
    get_pet_implemented,
    get_pet_species,
    get_pet_species_stats,
    get_pet_species_types,
    get_pet_types_from_species,
    get_species_by_name,
    reset_pet_species_caches,
)
from src.data.weather import (
    get_weather,
    get_weather_by_name,
    get_weather_damage_mult,
    reset_weather_caches,
)


def reset_species_config_caches() -> None:
    reset_pet_species_caches()
    reset_nature_caches()
    reset_evolution_caches()
    reset_battle_config_caches()
    reset_weather_caches()
