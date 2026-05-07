"""数据更新协调器 — 合并 RKPP 数据和 Wiki 数据。"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.data.loader import get_bundle, DATA_DIR

logger = logging.getLogger(__name__)


class DataUpdater:
    def check_updates(self) -> List[str]:
        """检查哪些数据文件需要更新。"""
        bundle = get_bundle()
        issues: List[str] = []
        for key, val in bundle.items():
            if isinstance(val, dict) and len(val) == 0:
                issues.append(f"{key}: 空数据")
        return issues

    def merge_pet_data(self, rkpp_data: Dict[str, Any], wiki_data: Dict[str, Any]) -> Dict[str, Any]:
        """合并 RKPP 精灵数据和 Wiki 数据。优先使用较全的数据。"""
        merged = dict(rkpp_data)

        if "types" not in merged and "types_raw" in wiki_data:
            merged["types_raw"] = wiki_data["types_raw"]

        for stat_key in ["hp", "attack", "defense", "speed"]:
            if stat_key in wiki_data and stat_key not in merged:
                merged[stat_key] = wiki_data[stat_key]

        if "skills" not in merged and "skills" in wiki_data:
            merged["skills"] = wiki_data["skills"]

        return merged

    def save_merged(self, data: Any, path: Path) -> None:
        """保存合并后的数据到 JSON 文件。"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("数据已保存: %s", path)

    def update_pet_map(self, wiki_details: List[Dict[str, Any]]) -> int:
        """用 Wiki 数据更新 pet_map.json。"""
        pet_map_path = DATA_DIR / "pet_map.json"
        with open(pet_map_path, "r", encoding="utf-8") as f:
            pet_map = json.load(f)

        updated = 0
        for detail in wiki_details:
            name = detail.get("name")
            if not name:
                continue
            for pid, pet in pet_map.items():
                if pet.get("name") == name:
                    merged = self.merge_pet_data(pet, detail)
                    pet_map[pid] = merged
                    updated += 1
                    break

        if updated > 0:
            self.save_merged(pet_map, pet_map_path)
        return updated
