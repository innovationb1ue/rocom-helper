"""Buff 修正查询兼容门面。"""
from __future__ import annotations

from src.data.buff_presentation import (
    enrich_buff_modifiers,
    format_buff_modifier_summary,
)
from src.data.buff_resource_modifiers import (
    get_buff_damage_reduction,
    get_speed_buff_modifiers,
)
from src.data.buff_skill_modifiers import (
    get_buff_hit_count_modifiers,
    get_buff_power_modifiers,
)
from src.data.buff_stat_modifiers import (
    _merge_modifiers,
    _resolve_buff_modifiers,
    get_buff_derived_stat_modifiers,
    get_buff_stat_modifiers,
)
from src.data.buff_tables import reset_buff_tables
from src.data.weather import get_weather_damage_mult


def reset_buff_modifier_caches() -> None:
    reset_buff_tables()


__all__ = [
    "_merge_modifiers",
    "_resolve_buff_modifiers",
    "enrich_buff_modifiers",
    "format_buff_modifier_summary",
    "get_buff_damage_reduction",
    "get_buff_derived_stat_modifiers",
    "get_buff_hit_count_modifiers",
    "get_buff_power_modifiers",
    "get_buff_stat_modifiers",
    "get_speed_buff_modifiers",
    "get_weather_damage_mult",
    "reset_buff_modifier_caches",
]
