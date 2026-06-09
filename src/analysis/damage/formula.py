"""伤害公式基础计算。"""
from __future__ import annotations


def base_damage(atk: float, defense: float, power: int) -> float:
    """NRC_AI 基础伤害公式: (ATK / DEF) * power * 0.9。"""
    if defense <= 0:
        defense = 1.0
    return (atk / defense) * power * 0.9
