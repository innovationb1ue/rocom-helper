"热门技能预设配置读写。"
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.config import settings

# ── 热门技能预设 ──────────────────────────────────────────────

CONFIG_DIR = settings.config_dir
_POPULAR_SKILLS_PATH = CONFIG_DIR / "popular_skills.json"
_popular_skills_cache: Optional[Dict[str, Any]] = None


def _load_popular_skills() -> Dict[str, Any]:
    """加载 popular_skills.json，返回完整配置。"""
    global _popular_skills_cache
    if _popular_skills_cache is not None:
        return _popular_skills_cache
    path = _POPULAR_SKILLS_PATH
    if not path.exists():
        _popular_skills_cache = {"version": 1, "presets": {}}
        return _popular_skills_cache
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        _popular_skills_cache = {"version": 1, "presets": {}}
        return _popular_skills_cache
    _popular_skills_cache = data if isinstance(data, dict) else {"version": 1, "presets": {}}
    return _popular_skills_cache


def get_popular_skills(base_id: int) -> Optional[Dict[str, Any]]:
    """获取某精灵的热门技能预设。返回 {"name": ..., "skills": [...], "note": ...} 或 None。"""
    data = _load_popular_skills()
    presets = data.get("presets", {})
    return presets.get(str(base_id))


def get_all_popular_skills() -> Dict[str, Any]:
    """获取全部热门技能预设。"""
    return _load_popular_skills()


def save_popular_skills(base_id: int, name: str, skills: List[int], note: str = "") -> None:
    """保存某精灵的热门技能预设。"""
    data = _load_popular_skills()
    presets = data.setdefault("presets", {})
    presets[str(base_id)] = {"name": name, "skills": skills, "note": note}
    _save_popular_skills_file(data)


def delete_popular_skills(base_id: int) -> bool:
    """删除某精灵的热门技能预设。返回是否存在。"""
    data = _load_popular_skills()
    presets = data.get("presets", {})
    key = str(base_id)
    if key in presets:
        del presets[key]
        _save_popular_skills_file(data)
        return True
    return False


def _save_popular_skills_file(data: Dict[str, Any]) -> None:
    """将热门技能配置写入文件。"""
    global _popular_skills_cache
    _POPULAR_SKILLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _POPULAR_SKILLS_PATH.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    _popular_skills_cache = data


def reset_popular_skill_cache() -> None:
    global _popular_skills_cache
    _popular_skills_cache = None
