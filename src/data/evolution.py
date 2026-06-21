"""宠物进化链数据查询。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.data.catalog import DATA_DIR, _read_json_dict

_evolution_cache: Optional[Dict[str, Any]] = None
_evo_by_petbase_cache: Optional[Dict[int, str]] = None


def _load_evolution_map() -> Dict[str, Any]:
    global _evolution_cache
    if _evolution_cache is not None:
        return _evolution_cache
    path = DATA_DIR / "evolution_map.json"
    _evolution_cache = _read_json_dict(path)
    return _evolution_cache


def _build_evo_petbase_index() -> Dict[int, str]:
    """构建 petbase_id → evolution_id 索引。"""
    global _evo_by_petbase_cache
    if _evo_by_petbase_cache is not None:
        return _evo_by_petbase_cache
    _evo_by_petbase_cache = {}
    em = _load_evolution_map()
    for evo_id, evo in em.items():
        chain = evo.get("evolution_chain", [])
        for stage in chain:
            pb_id = stage.get("petbase_id")
            if pb_id is not None:
                _evo_by_petbase_cache[int(pb_id)] = evo_id
    return _evo_by_petbase_cache


def get_evolution_chain(evolution_id: Optional[int] = None,
                        petbase_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """按进化链 ID 或 petbase_id 查找进化链。"""
    em = _load_evolution_map()
    if evolution_id is not None:
        return em.get(str(evolution_id))
    if petbase_id is not None:
        idx = _build_evo_petbase_index()
        evo_id = idx.get(petbase_id)
        if evo_id:
            return em.get(str(evo_id))
    return None


def get_evolution_pvp_mute_group(petbase_id: int) -> Optional[int]:
    """获取进化链的 PvP mute group（同进化链在 PvP 中视为同一只精灵）。"""
    chain = get_evolution_chain(petbase_id=petbase_id)
    if chain:
        return chain.get("pvp_mute_group")
    return None


def reset_evolution_caches() -> None:
    global _evolution_cache, _evo_by_petbase_cache
    _evolution_cache = None
    _evo_by_petbase_cache = None
