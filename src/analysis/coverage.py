"""属性覆盖度分析 — 进攻覆盖 + 防守弱点 + 综合评分。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.game.type_chart import TypeChart


class CoverageAnalyzer:
    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self.chart = type_chart or TypeChart()

    def offensive_coverage(self, team_pets: List[Dict[str, Any]]) -> Dict[str, float]:
        """进攻覆盖度：对每种防御属性，队伍所有精灵技能的最佳倍率。

        team_pets: [{"types": [int, ...], "skills": [{"type_id": int, ...}, ...]}]
        返回: {属性名: 最佳倍率}
        """
        attack_types: List[int] = []
        for pet in team_pets:
            for skill in pet.get("skills", []):
                tid = skill.get("type_id")
                if tid is not None:
                    attack_types.append(tid)
            # Also include pet's own types as potential STAB coverage
            for tid in pet.get("types", []):
                if tid not in attack_types:
                    attack_types.append(tid)

        if not attack_types:
            attack_types = [t["id"] for t in self.chart.all_types()]

        coverage = self.chart.get_coverage(attack_types)
        return {self.chart.type_name(tid): mult for tid, mult in coverage.items()}

    def defensive_coverage(self, team_pets: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """防守弱点分析：找出队伍的共同弱点。

        返回: {攻击属性名: [被克制的精灵名称列表]}
        """
        result: Dict[str, List[str]] = {}
        for pet in team_pets:
            types = pet.get("types", [])
            if not types:
                continue
            name = pet.get("name", f"Pet_{pet.get('id', '?')}")
            weaknesses = self.chart.get_weaknesses(types)
            for type_id, mult in weaknesses.items():
                type_name = self.chart.type_name(type_id)
                if type_name not in result:
                    result[type_name] = []
                result[type_name].append(name)
        return result

    def coverage_score(self, team_pets: List[Dict[str, Any]]) -> float:
        """综合覆盖度评分 (0-100)。"""
        offensive = self.offensive_coverage(team_pets)
        if not offensive:
            return 0.0

        total = len(offensive)
        effective = sum(1 for m in offensive.values() if m >= 2.0)
        neutral = sum(1 for m in offensive.values() if 0 < m < 2.0 and m >= 1.0)
        resisted = sum(1 for m in offensive.values() if 0 < m < 1.0)
        immune = sum(1 for m in offensive.values() if m == 0.0)

        off_score = (effective * 2.0 + neutral * 1.0) / (total * 2.0) * 100.0

        defensive = self.defensive_coverage(team_pets)
        shared_weaknesses = sum(1 for names in defensive.values() if len(names) >= len(team_pets) * 0.5)
        def_score = max(0.0, 100.0 - shared_weaknesses * 15.0)

        return off_score * 0.6 + def_score * 0.4

    def uncovered_types(self, team_pets: List[Dict[str, Any]]) -> List[str]:
        """返回没有任何精灵能克制的属性列表。"""
        offensive = self.offensive_coverage(team_pets)
        return [name for name, mult in offensive.items() if mult < 2.0]

    def shared_weaknesses(self, team_pets: List[Dict[str, Any]]) -> Dict[str, float]:
        """返回全队共同弱点（所有精灵都被克制的属性）。"""
        if not team_pets:
            return {}
        common: Dict[int, List[float]] = {}
        for pet in team_pets:
            types = pet.get("types", [])
            if not types:
                continue
            weaknesses = self.chart.get_weaknesses(types)
            for type_id, mult in weaknesses.items():
                if type_id not in common:
                    common[type_id] = []
                common[type_id].append(mult)

        n = len([p for p in team_pets if p.get("types")])
        if n == 0:
            return {}
        return {
            self.chart.type_name(tid): min(mults)
            for tid, mults in common.items()
            if len(mults) >= n
        }
