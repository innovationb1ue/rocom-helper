"""战斗全局配置查询。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.data.catalog import DATA_DIR, _read_json_dict

_battle_config_cache: Optional[Dict[str, Any]] = None


def _load_battle_config() -> Dict[str, Any]:
    global _battle_config_cache
    if _battle_config_cache is not None:
        return _battle_config_cache
    path = DATA_DIR / "battle_config.json"
    _battle_config_cache = _read_json_dict(path)
    return _battle_config_cache


def get_battle_config() -> Dict[str, Any]:
    """获取战斗全局配置（克制倍率、捕捉参数等）。"""
    return _load_battle_config()


def get_restraint_multipliers() -> Dict[str, float]:
    """获取克制伤害倍率。"""
    cfg = _load_battle_config()
    result = {"single_super": 1.0, "double_super": 2.0, "single_resist": 0.5, "double_resist": 0.75}

    for key, config_key in [
        ("single_super", "restraint_percent"),
        ("double_super", "double_restraint_percent"),
        ("single_resist", "restrained_percent"),
        ("double_resist", "double_restrained_percent"),
    ]:
        entry = cfg.get(config_key, {})
        val = entry.get("value")
        if isinstance(val, (int, float)) and val > 0:
            result[key] = val / 10000.0

    return result


def reset_battle_config_caches() -> None:
    global _battle_config_cache
    _battle_config_cache = None
