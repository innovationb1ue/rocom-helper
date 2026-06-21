"""伤害公式使用的战斗属性解析。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.data.loader import (
    get_buff_stat_modifiers,
    get_nature_stat_modifiers,
    get_pet_species_stats,
)
from src.game.stats import calc_pvp_template_stat

ATK_STAT = {2: "ATK", 3: "SPA"}  # damage_type -> 攻击属性
DEF_STAT = {2: "DEF", 3: "SPD"}  # damage_type -> 防御属性

STAT_NAME_ALIASES = {
    "ATK": ("ATK", "ATTACK"),
    "DEF": ("DEF", "DEFENSE"),
    "SPA": ("SPA", "SPATK", "SP_ATTACK", "SPECIAL_ATTACK"),
    "SPD": ("SPD", "SPDEF", "SP_DEFENSE", "SPECIAL_DEFENSE"),
    "SPE": ("SPE", "SPEED", "SPD_SPEED"),
}


def get_stat_with_source(pet: Dict[str, Any], stat_name: str) -> Tuple[Optional[int], str]:
    """从抓包数据中提取属性值和来源。来源: 'total', 'calc_bonus', ''。"""
    stats = pet.get("stats", [])
    aliases = STAT_NAME_ALIASES.get(stat_name, (stat_name,))
    for stat in stats:
        if stat.get("name") not in aliases:
            continue
        total = stat.get("total")
        if total is not None:
            if stat_name != "HP" and total <= 0:
                break
            return int(total), "total"
        calc = stat.get("calc") or 0
        bonus = stat.get("bonus") or 0
        if stat_name != "HP" and calc + bonus <= 0:
            break
        return calc + bonus, "calc_bonus"
    return None, ""


def get_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
    """从抓包数据中提取属性值。"""
    value, _ = get_stat_with_source(pet, stat_name)
    return value


def resolve_stat_buff_modifiers(buff_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """解析伤害计算展示和公式共用的属性 buff 修正。"""
    return get_buff_stat_modifiers(buff_list)


def calc_arena_stat(race_value: int, stat_name: str) -> int:
    """用 PvP 通用模板估算平衡后属性值。"""
    return calc_pvp_template_stat(race_value, stat_name)


def nature_modifiers(pet: Dict[str, Any]) -> Dict[str, float]:
    for key in ("nature_stat_modifiers", "nature_modifiers"):
        mods = pet.get(key)
        if isinstance(mods, dict):
            return {str(k).lower(): float(v) for k, v in mods.items()}
    nature_id = pet.get("nature_id") or pet.get("nature")
    if nature_id is not None:
        return get_nature_stat_modifiers(nature_id)
    return {}


def get_pvp_template_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
    """从 pet_species 种族值按 PvP 通用模板估算平衡后属性值。"""
    base_id = pet.get("base_id") or pet.get("base_conf_id")
    if not base_id:
        return None
    species_stats = get_pet_species_stats(base_id)
    key = stat_name.lower() if stat_name.isupper() else stat_name
    race = species_stats.get(key) or species_stats.get(stat_name.upper())
    if race:
        nature_mod = nature_modifiers(pet).get(key, 0.0)
        return calc_pvp_template_stat(int(race), stat_name, nature_mod)
    return None


def get_wiki_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
    """旧兜底接口。当前没有独立 wiki 属性源，保留为兼容入口。"""
    return None


def resolve_combat_stats(
    attacker: Dict[str, Any],
    defender: Dict[str, Any],
    damage_type: int,
) -> Optional[Tuple[float, float, float, str, List[str], Dict[str, str]]]:
    """获取有效攻防属性、能力等级和置信度。"""
    confidence = "high"
    warnings: List[str] = []

    atk_name = ATK_STAT[damage_type]
    def_name = DEF_STAT[damage_type]
    base_atk, atk_source = get_stat_with_source(attacker, atk_name)
    base_def, def_source = get_stat_with_source(defender, def_name)

    if base_atk is None:
        base_atk = get_pvp_template_stat(attacker, atk_name)
        atk_source = "pvp_template" if base_atk is not None else ""
    if base_def is None:
        base_def = get_pvp_template_stat(defender, def_name)
        def_source = "pvp_template" if base_def is not None else ""
    if base_atk is None:
        base_atk = get_wiki_stat(attacker, atk_name)
        atk_source = "wiki" if base_atk is not None else ""
    if base_def is None:
        base_def = get_wiki_stat(defender, def_name)
        def_source = "wiki" if base_def is not None else ""

    if base_atk is None or base_def is None:
        return None

    sources = {atk_source, def_source}
    if "wiki" in sources:
        confidence = "low"
        if atk_source == "wiki":
            warnings.append("攻击属性来自 wiki 估算")
        if def_source == "wiki":
            warnings.append("防御属性来自 wiki 估算")
    elif "calc_bonus" in sources or "pvp_template" in sources:
        confidence = "medium"
        if atk_source == "calc_bonus":
            warnings.append("攻击属性来自 calc+bonus 估算")
        if def_source == "calc_bonus":
            warnings.append("防御属性来自 calc+bonus 估算")
        if atk_source == "pvp_template":
            warnings.append("攻击属性来自 PvP 通用模板估算")
        if def_source == "pvp_template":
            warnings.append("防御属性来自 PvP 通用模板估算")

    atk_mods = get_buff_stat_modifiers(attacker.get("buffs", []))
    def_mods = get_buff_stat_modifiers(defender.get("buffs", []))
    atk_up = atk_mods.get(f"{atk_name.lower()}_up", 0.0)
    atk_down = atk_mods.get(f"{atk_name.lower()}_down", 0.0)
    def_key = def_name.lower()
    def_up = def_mods.get(f"{def_key}_up", 0.0)
    def_down = def_mods.get(f"{def_key}_down", 0.0)

    ability_level = (1.0 + atk_up + def_down) / max(0.1, 1.0 + atk_down + def_up)
    ability_level = max(0.1, min(5.0, ability_level))

    effective_atk = base_atk * ability_level
    effective_def = max(1.0, float(base_def))

    if ability_level != 1.0:
        warnings.append(f"能力等级 ×{ability_level:.2f}")

    stat_sources = {
        "attack": atk_source,
        "defense": def_source,
        "attack_stat": atk_name,
        "defense_stat": def_name,
    }
    return effective_atk, effective_def, ability_level, confidence, warnings, stat_sources
