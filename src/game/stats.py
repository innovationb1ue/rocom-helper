"""种族值/能力值计算 — 洛克王国宠物属性公式。"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

STAT_NAMES = ["HP", "ATK", "DEF", "SPA", "SPD", "SPE"]
STAT_NAMES_CN = ["生命", "物攻", "魔攻", "物防", "魔防", "速度"]

PVP_TEMPLATE = {
    "level": 60,
    "effort_grow_level": 50,
    "growth_star": 5,
    "awaken_star": 0,
    "positive_nature_modifier": 0.20,
}

_PVP_STAT_KEYS = {
    "HP": "hp",
    "ATK": "atk",
    "DEF": "def",
    "SPA": "spa",
    "SPD": "spd",
    "SPE": "spe",
}

# 性格修正: name → (increased_stat_index, decreased_stat_index)
# None means neutral nature
NATURE_EFFECTS: Dict[str, Optional[Tuple[int, int]]] = {
    "孤僻": (1, 2),   # ATK+, DEF-
    "固执": (1, 3),   # ATK+, SPD-
    "调皮": (1, 5),   # ATK+, SPE-
    "勇敢": (1, 3),   # ATK+, SPA-
    "保守": (3, 1),   # SPA+, ATK-
    "稳重": (3, 2),   # SPA+, DEF-
    "马虎": (3, 5),   # SPA+, SPE-
    "冷静": (3, 5),   # SPA+, SPE-
    "胆小": (5, 1),   # SPE+, ATK-
    "急躁": (5, 2),   # SPE+, DEF-
    "开朗": (5, 3),   # SPE+, SPD-
    "天真": (5, 4),   # SPE+, SPD-
    "坦率": None,      # Neutral
    "害羞": None,
    "认真": None,
    "浮躁": None,
    "实干": None,
    "孤高": None,
}


def calc_hp(base: int, iv: int = 31, ev: int = 0, level: int = 100) -> int:
    """HP 计算公式: ((种族值*2 + 个体值 + 努力值//4) * 等级 // 100) + 等级 + 10"""
    return ((base * 2 + iv + ev // 4) * level // 100) + level + 10


def calc_stat(base: int, iv: int = 31, ev: int = 0, level: int = 100,
              nature_modifier: float = 1.0) -> int:
    """非HP属性计算: ((种族值*2 + 个体值 + 努力值//4) * 等级 // 100) + 5, 再乘性格修正"""
    raw = ((base * 2 + iv + ev // 4) * level // 100) + 5
    return int(raw * nature_modifier)


def get_nature_modifier(nature: str, stat_index: int) -> float:
    """获取性格对指定属性的修正值。stat_index: 0=HP,1=ATK,2=DEF,3=SPA,4=SPD,5=SPE"""
    effect = NATURE_EFFECTS.get(nature)
    if effect is None:
        return 1.0
    increased, decreased = effect
    if stat_index == increased:
        return 1.1
    if stat_index == decreased:
        return 0.9
    return 1.0


def calc_all_stats(bases: List[int], ivs: Optional[List[int]] = None,
                   evs: Optional[List[int]] = None, level: int = 100,
                   nature: str = "坦率") -> Dict[str, int]:
    """计算所有属性值。bases: [HP,ATK,DEF,SPA,SPD,SPE]"""
    if len(bases) != 6:
        raise ValueError(f"Expected 6 base stats, got {len(bases)}")
    if ivs is None:
        ivs = [31] * 6
    if evs is None:
        evs = [0] * 6

    result: Dict[str, int] = {}
    for i, name in enumerate(STAT_NAMES):
        if i == 0:
            result[name] = calc_hp(bases[0], ivs[0], evs[0], level)
        else:
            mod = get_nature_modifier(nature, i)
            result[name] = calc_stat(bases[i], ivs[i], evs[i], level, mod)
    return result


def calc_pvp_template_stat(
    race_value: int,
    stat_name: str,
    nature_modifier: float = 0.0,
) -> int:
    """用 PvP 平衡模板从种族值估算战斗属性。

    v1 沿用当前竞技场经验公式：
    HP = 1.7×种族值 + 170，其他属性 = 1.1×种族值 + 60。
    正面性格在 PvP 中按 +20% 处理；负面性格沿用传入的负面比例。
    """
    stat = stat_name.upper()
    if stat == "HP":
        return round(1.7 * race_value + 170)

    base = 1.1 * race_value + 60
    if nature_modifier > 0:
        base *= 1.0 + PVP_TEMPLATE["positive_nature_modifier"]
    elif nature_modifier < 0:
        base *= max(0.1, 1.0 + nature_modifier)
    return round(base)


def calc_pvp_template_stats(
    species_stats: Dict[str, int],
    nature_modifiers: Optional[Dict[str, float]] = None,
) -> Dict[str, int]:
    """按 PvP 平衡模板生成六维属性，返回大写 stat 名称。"""
    nature_modifiers = nature_modifiers or {}
    result: Dict[str, int] = {}
    for stat_name, species_key in _PVP_STAT_KEYS.items():
        race = species_stats.get(species_key) or species_stats.get(stat_name)
        if race is None:
            continue
        result[stat_name] = calc_pvp_template_stat(
            int(race),
            stat_name,
            nature_modifiers.get(species_key, 0.0),
        )
    return result


def normalize_stat(value: int, max_value: int = 300) -> float:
    """将种族值归一化到 0-100 评分。"""
    if max_value <= 0:
        return 0.0
    return min(100.0, value / max_value * 100.0)


def stat_total(bases: List[int]) -> int:
    """种族值总和。"""
    return sum(bases)


def stat_rating(bases: List[int]) -> float:
    """综合种族值评分 (0-100)。基于总和归一化，总和 600 为满分。"""
    total = stat_total(bases)
    return min(100.0, total / 600.0 * 100.0)
