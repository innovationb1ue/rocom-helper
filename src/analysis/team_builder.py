"""队伍分析和推荐 — 综合评分、角色分析、队友推荐。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.game.type_chart import TypeChart
from src.analysis.coverage import CoverageAnalyzer


class TeamBuilder:
    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self.chart = type_chart or TypeChart()
        self.coverage = CoverageAnalyzer(self.chart)

    def analyze_team(self, pets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析队伍，返回综合报告。

        pets: [{"id", "name", "types": [int], "stats": {"SPE": int, ...},
                "skills": [{"type_id": int, "power": int, ...}]}]
        """
        off_cov = self.coverage.offensive_coverage(pets)
        def_cov = self.coverage.defensive_coverage(pets)
        score = self.coverage.coverage_score(pets)
        uncovered = self.coverage.uncovered_types(pets)
        shared = self.coverage.shared_weaknesses(pets)

        speed_tier = self._speed_tier(pets)
        role_analysis = self._role_analysis(pets)
        suggestions = self._generate_suggestions(uncovered, shared, def_cov, pets)

        return {
            "score": round(score, 1),
            "offensive_coverage": off_cov,
            "defensive_coverage": def_cov,
            "shared_weaknesses": shared,
            "uncovered_types": uncovered,
            "speed_tier": speed_tier,
            "role_analysis": role_analysis,
            "suggestions": suggestions,
        }

    def suggest_teammates(self, core_pets: List[Dict[str, Any]],
                          pool: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        """从精灵池中推荐队友来弥补核心精灵的弱点。"""
        if not core_pets or not pool:
            return []

        # Find weaknesses and uncovered types of current team
        weaknesses = self.coverage.shared_weaknesses(core_pets)
        uncovered = self.coverage.uncovered_types(core_pets)
        weakness_types = [self.chart.type_id(n) for n in weaknesses if self.chart.type_id(n) is not None]
        uncovered_types = [self.chart.type_id(n) for n in uncovered if self.chart.type_id(n) is not None]
        needed_types = set(t for t in weakness_types + uncovered_types if t is not None)

        scored = []
        for candidate in pool:
            candidate_score = 0.0
            candidate_types = candidate.get("types", [])
            candidate_skills = candidate.get("skills", [])

            # Can this candidate cover shared weaknesses?
            for needed in needed_types:
                for tid in candidate_types:
                    if tid == needed:
                        candidate_score += 5.0
                for skill in candidate_skills:
                    if skill.get("type_id") == needed:
                        candidate_score += 3.0

            # Resist shared weakness types?
            for wt in weakness_types:
                if wt is not None:
                    mult = self.chart.get_multiplier(wt, candidate_types)
                    if mult < 1.0:
                        candidate_score += 3.0 * (1.0 - mult)
                    elif mult == 0.0:
                        candidate_score += 10.0

            # Don't add new shared weaknesses
            if candidate_types:
                new_team = core_pets + [candidate]
                new_shared = self.coverage.shared_weaknesses(new_team)
                if len(new_shared) <= len(weaknesses):
                    candidate_score += 2.0

            if candidate_score > 0:
                entry = dict(candidate)
                entry["_teammate_score"] = round(candidate_score, 1)
                scored.append(entry)

        scored.sort(key=lambda x: x["_teammate_score"], reverse=True)
        return scored[:top_n]

    def _speed_tier(self, pets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按速度降序排列。"""
        entries = []
        for pet in pets:
            stats = pet.get("stats", {})
            spe = stats.get("SPE") or stats.get("speed") or 0
            if isinstance(spe, str):
                try:
                    spe = int(spe)
                except (ValueError, TypeError):
                    spe = 0
            entries.append({
                "name": pet.get("name", "?"),
                "speed": spe,
                "types": [self.chart.type_name(t) for t in pet.get("types", [])],
            })
        entries.sort(key=lambda x: x["speed"], reverse=True)
        return entries

    def _role_analysis(self, pets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """简单角色分析：根据种族值分布判断角色。"""
        roles = []
        for pet in pets:
            stats = pet.get("stats", {})
            name = pet.get("name", "?")
            atk = stats.get("ATK") or stats.get("attack") or 0
            spa = stats.get("SPA") or stats.get("sp_attack") or 0
            spe = stats.get("SPE") or stats.get("speed") or 0
            hp = stats.get("HP") or stats.get("hp") or 0

            if isinstance(atk, str):
                atk = int(atk) if atk.isdigit() else 0
            if isinstance(spa, str):
                spa = int(spa) if spa.isdigit() else 0
            if isinstance(spe, str):
                spe = int(spe) if spe.isdigit() else 0
            if isinstance(hp, str):
                hp = int(hp) if hp.isdigit() else 0

            role = "辅助"
            max_off = max(atk, spa)
            if max_off > 0 and max_off >= spe and max_off >= hp:
                role = "物理C" if atk > spa else "特殊C"
            elif spe > max_off:
                role = "速度C"
            elif hp > max_off:
                role = "坦克"

            roles.append({"name": name, "role": role})
        return roles

    def _generate_suggestions(self, uncovered: List[str],
                              shared: Dict[str, float],
                              def_cov: Dict[str, List[str]],
                              pets: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """生成改进建议。"""
        suggestions: List[Dict[str, str]] = []
        for ut in uncovered[:5]:
            suggestions.append({
                "type": "weak_coverage",
                "message": f"队伍缺少{ut}系技能覆盖",
            })
        for wn, mult in shared.items():
            suggestions.append({
                "type": "shared_weakness",
                "message": f"全队被{wn}系共同克制 (×{mult:.1f})",
            })
        for atk_type, pet_names in def_cov.items():
            if len(pet_names) >= 3:
                suggestions.append({
                    "type": "concentrated_weakness",
                    "message": f"{len(pet_names)}只精灵被{atk_type}系克制: {', '.join(pet_names[:3])}",
                })
        return suggestions
