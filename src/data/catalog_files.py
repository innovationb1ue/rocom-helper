"""基础数据文件路径和安全 JSON 读取。"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = settings.project_root
DATA_DIR = settings.data_dir

_JSON_PATHS: Dict[str, Path] = {
    "attr_meta": DATA_DIR / "attr_map.json",
    "skill_meta": DATA_DIR / "skill_map.json",
    "buff_meta": DATA_DIR / "buff_map.json",
    "buffbase_meta": DATA_DIR / "buffbase_map.json",
    "pet_meta": DATA_DIR / "pet_map.json",
    "monster_meta": DATA_DIR / "monster_map.json",
    "pet_skill_meta": DATA_DIR / "pet_skill_map.json",
    "monster_skillbank_meta": DATA_DIR / "monster_skillbank_map.json",
    "special_move_meta": DATA_DIR / "special_move_map.json",
    "opcode_pb_meta": DATA_DIR / "opcode_pb_map.json",
    "pb_message_meta": DATA_DIR / "pb_message_index.json",
    "innate_skills": DATA_DIR / "innate_skills.json",
}


def _safe_int(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    s = text.strip()
    try:
        return int(s, 10) if s else None
    except ValueError:
        return None


def _read_json_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load JSON data %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}
