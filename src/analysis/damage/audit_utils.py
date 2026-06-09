"""伤害审计模块共享的小型转换工具。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def first_present(items: List[Dict[str, Any]], key: str) -> Any:
    for item in items:
        if item.get(key) is not None:
            return item[key]
    return None


def optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def has_value(value: Any) -> bool:
    return value not in (None, {}, [])


def resolve_runtime_cost(runtime_skill: Dict[str, Any]) -> Optional[int]:
    for key in ("cost_energy_result", "cost_energy", "raw_cost_energy"):
        if runtime_skill.get(key) is not None:
            return optional_int(runtime_skill[key])
    return None


def restraint_to_multiplier(value: Any) -> Optional[float]:
    ivalue = optional_int(value)
    if ivalue is None:
        return None
    return {
        -2: 0.25,
        -1: 0.5,
        0: 1.0,
        1: 1.5,
        2: 2.0,
        3: 4.0,
    }.get(ivalue)
