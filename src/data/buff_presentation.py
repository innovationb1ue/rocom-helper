"""Buff 修正展示与富化。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.data.buff_stat_modifiers import (
    get_buff_derived_stat_modifiers,
    get_buff_stat_modifiers,
)

_BUFF_MODIFIER_LABELS = {
    "atk_up": "物攻",
    "atk_down": "物攻",
    "spa_up": "魔攻",
    "spa_down": "魔攻",
    "def_up": "物防",
    "def_down": "物防",
    "spd_up": "魔防",
    "spd_down": "魔防",
}


def _format_modifier_pct(value: float) -> str:
    pct = value * 100
    if abs(pct - round(pct)) < 0.001:
        return str(int(round(pct)))
    return f"{pct:.1f}".rstrip("0").rstrip(".")


def format_buff_modifier_summary(modifiers: Dict[str, float]) -> List[str]:
    """将属性修正转成人类可读摘要，例如 ["魔攻 +10%"]。"""
    summary: List[str] = []
    for key in ("atk_up", "atk_down", "spa_up", "spa_down", "def_up", "def_down", "spd_up", "spd_down"):
        value = modifiers.get(key)
        if not value:
            continue
        label = _BUFF_MODIFIER_LABELS.get(key, key)
        sign = "+" if key.endswith("_up") else "-"
        summary.append(f"{label} {sign}{_format_modifier_pct(abs(value))}%")
    return summary


def enrich_buff_modifiers(buff: Dict[str, Any]) -> Dict[str, Any]:
    """为 buff 字典补充确定属性数值，保留原字段并只添加紧凑解释字段。"""
    enriched = dict(buff)
    derived_modifiers = get_buff_derived_stat_modifiers([enriched])
    modifiers = get_buff_stat_modifiers([enriched])
    if derived_modifiers:
        enriched["derived_modifier_summary"] = format_buff_modifier_summary(derived_modifiers)
    else:
        enriched.pop("derived_modifier_summary", None)
    if modifiers:
        enriched["modifiers"] = modifiers
        enriched["modifier_summary"] = format_buff_modifier_summary(modifiers)
    else:
        enriched.pop("modifiers", None)
        enriched.pop("modifier_summary", None)
    return enriched
