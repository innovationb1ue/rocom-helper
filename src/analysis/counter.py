"""反制推荐引擎 — 找出对手队伍的最佳反制精灵。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.game.type_chart import TypeChart


class CounterPicker:
    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self.chart = type_chart or TypeChart()

    def find_counters(self, opponent_team: List[Dict[str, Any]],
                      my_pool: List[Dict[str, Any]],
                      top_n: int = 6) -> List[Dict[str, Any]]:
        """从精灵池中找出对手队伍的最佳反制精灵。

        评分因子:
        1. 属性克制倍率（对对手精灵的进攻倍率）
        2. 属性抗性（抵抗对手常见攻击属性）
        3. 速度优势
        4. 技能覆盖（技能属性能克制多个对手精灵）
        """
        if not opponent_team or not my_pool:
            return []

        scored = []
        for candidate in my_pool:
            score = 0.0
            c_types = candidate.get("types", [])
            c_skills = candidate.get("skills", [])
            c_stats = candidate.get("stats", {})
            c_spe = c_stats.get("SPE") or c_stats.get("speed") or 0
            if isinstance(c_spe, str):
                try:
                    c_spe = int(c_spe)
                except (ValueError, TypeError):
                    c_spe = 0

            detail_breakdown: Dict[str, float] = {}

            for opp in opponent_team:
                opp_types = opp.get("types", [])
                opp_stats = opp.get("stats", {})
                opp_spe = opp_stats.get("SPE") or opp_stats.get("speed") or 0
                if isinstance(opp_spe, str):
                    try:
                        opp_spe = int(opp_spe)
                    except (ValueError, TypeError):
                        opp_spe = 0

                # 1. Offensive: my types vs opponent types
                for tid in c_types:
                    mult = self.chart.get_multiplier(tid, opp_types)
                    if mult >= 2.0:
                        score += 10.0 * mult
                        detail_breakdown["offensive"] = detail_breakdown.get("offensive", 0) + 10.0 * mult
                    elif mult > 1.0:
                        score += 3.0 * mult
                        detail_breakdown["offensive"] = detail_breakdown.get("offensive", 0) + 3.0 * mult

                # 2. Skill type coverage vs opponent
                for skill in c_skills:
                    skill_type = skill.get("type_id")
                    if skill_type is not None:
                        mult = self.chart.get_multiplier(skill_type, opp_types)
                        if mult >= 2.0:
                            score += 5.0
                            detail_breakdown["skill_coverage"] = detail_breakdown.get("skill_coverage", 0) + 5.0

                # 3. Defensive: opponent types vs my types
                for tid in opp_types:
                    mult = self.chart.get_multiplier(tid, c_types)
                    if mult == 0.0:
                        score += 8.0  # immunity
                        detail_breakdown["defensive"] = detail_breakdown.get("defensive", 0) + 8.0
                    elif mult < 1.0:
                        score += 3.0 * (1.0 - mult)
                        detail_breakdown["defensive"] = detail_breakdown.get("defensive", 0) + 3.0 * (1.0 - mult)
                    elif mult > 1.0:
                        score -= 3.0 * (mult - 1.0)
                        detail_breakdown["defensive"] = detail_breakdown.get("defensive", 0) - 3.0 * (mult - 1.0)

                # 4. Speed advantage
                if c_spe > 0 and opp_spe > 0:
                    if c_spe > opp_spe:
                        speed_bonus = min(5.0, (c_spe - opp_spe) / 20.0)
                        score += speed_bonus
                        detail_breakdown["speed"] = detail_breakdown.get("speed", 0) + speed_bonus

            if score > 0:
                entry = dict(candidate)
                entry["_counter_score"] = round(score, 1)
                entry["_counter_detail"] = {k: round(v, 1) for k, v in detail_breakdown.items()}
                scored.append(entry)

        scored.sort(key=lambda x: x["_counter_score"], reverse=True)
        return scored[:top_n]

    def find_counter_skills(self, my_pet: Dict[str, Any],
                            opponent_pet: Dict[str, Any]) -> List[Dict[str, Any]]:
        """给定我方精灵，找出对对手最有效的技能。"""
        opp_types = opponent_pet.get("types", [])
        skills = my_pet.get("skills", [])
        if not opp_types or not skills:
            return []

        scored = []
        for skill in skills:
            skill_type = skill.get("type_id")
            if skill_type is None:
                continue
            mult = self.chart.get_multiplier(skill_type, opp_types)
            if mult > 0:
                entry = dict(skill)
                entry["_effectiveness"] = mult
                entry["_label"] = self.chart.get_effectiveness_label(mult)
                scored.append(entry)

        scored.sort(key=lambda x: x["_effectiveness"], reverse=True)
        return scored
