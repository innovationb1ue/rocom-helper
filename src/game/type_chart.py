"""属性克制计算器：加载 type_chart.json，提供倍率查询、弱点分析、覆盖度计算。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CHART_PATH = _PROJECT_ROOT / "data" / "game" / "type_chart.json"


class TypeChart:
    def __init__(self, chart_path: Optional[Path] = None) -> None:
        path = chart_path or _DEFAULT_CHART_PATH
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        self.version: str = raw["version"]
        self.types: List[Dict] = raw["types"]
        self._id_to_name: Dict[int, str] = {t["id"]: t["name"] for t in self.types}
        self._name_to_id: Dict[str, int] = {t["name"]: t["id"] for t in self.types}
        self._id_to_color: Dict[int, str] = {t["id"]: t["color"] for t in self.types}

        # chart[atk_id][def_id] = multiplier; omitted means 1.0
        self._chart: Dict[int, Dict[int, float]] = {}
        for atk_str, defenses in raw["chart"].items():
            atk_id = int(atk_str)
            self._chart[atk_id] = {int(k): v for k, v in defenses.items()}

    def _lookup(self, atk: int, defense: int) -> float:
        return self._chart.get(atk, {}).get(defense, 1.0)

    def get_multiplier(self, attack_type: int, defend_types: List[int]) -> float:
        result = 1.0
        for dt in defend_types:
            result *= self._lookup(attack_type, dt)
        return result

    def get_effectiveness_label(self, multiplier: float) -> str:
        if multiplier <= 0.0:
            return "无效"
        if multiplier < 0.5:
            return "效果甚微"
        if multiplier < 1.0:
            return "效果不佳"
        if multiplier == 1.0:
            return "普通"
        if multiplier < 2.0:
            return "效果不错"
        if multiplier < 3.0:
            return "效果拔群"
        return "超级有效"

    def get_weaknesses(self, defend_types: List[int]) -> Dict[int, float]:
        result: Dict[int, float] = {}
        for t in self.types:
            tid = t["id"]
            m = self.get_multiplier(tid, defend_types)
            if m > 1.0:
                result[tid] = m
        return result

    def get_resistances(self, defend_types: List[int]) -> Dict[int, float]:
        result: Dict[int, float] = {}
        for t in self.types:
            tid = t["id"]
            m = self.get_multiplier(tid, defend_types)
            if 0.0 < m < 1.0:
                result[tid] = m
        return result

    def get_immunities(self, defend_types: List[int]) -> List[int]:
        result: List[int] = []
        for t in self.types:
            tid = t["id"]
            m = self.get_multiplier(tid, defend_types)
            if m == 0.0:
                result.append(tid)
        return result

    def get_coverage(self, attack_types: List[int]) -> Dict[int, float]:
        best: Dict[int, float] = {}
        for t in self.types:
            tid = t["id"]
            for atk in attack_types:
                m = self._lookup(atk, tid)
                if tid not in best or m > best[tid]:
                    best[tid] = m
        return best

    def all_types(self) -> List[Dict]:
        return list(self.types)

    def type_name(self, type_id: int) -> str:
        return self._id_to_name.get(type_id, f"未知({type_id})")

    def type_id(self, name: str) -> Optional[int]:
        return self._name_to_id.get(name)

    def type_color(self, type_id: int) -> str:
        return self._id_to_color.get(type_id, "#999999")

    def offensive_coverage_score(self, attack_types: List[int]) -> float:
        if not attack_types:
            return 0.0
        coverage = self.get_coverage(attack_types)
        total = len(self.types)
        if total == 0:
            return 0.0
        effective = sum(1 for m in coverage.values() if m >= 2.0)
        neutral = sum(1 for m in coverage.values() if 0.0 < m < 2.0 and m >= 1.0)
        return (effective * 2.0 + neutral * 1.0) / (total * 2.0) * 100.0

    def defensive_rating(self, defend_types: List[int]) -> float:
        weaknesses = self.get_weaknesses(defend_types)
        resistances = self.get_resistances(defend_types)
        immunities = self.get_immunities(defend_types)
        n = len(self.types)
        if n == 0:
            return 50.0
        score = 50.0
        score -= sum((m - 1.0) * 10 for m in weaknesses.values())
        score += sum((1.0 - m) * 5 for m in resistances.values())
        score += len(immunities) * 15
        return max(0.0, min(100.0, score))
