"""威胁评估 — 评估对手队伍对我方队伍的威胁程度。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.game.type_chart import TypeChart


class ThreatAssessor:
    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self.chart = type_chart or TypeChart()

    def assess_threats(self, opponent_team: List[Dict[str, Any]],
                       my_team: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """评估对手每只精灵对我方队伍的威胁。

        返回按威胁分数排序的列表。
        """
        threats = []
        for opp in opponent_team:
            opp_types = opp.get("types", [])
            opp_stats = opp.get("stats", {})
            opp_spe = opp_stats.get("SPE") or opp_stats.get("speed") or 0
            if isinstance(opp_spe, str):
                try:
                    opp_spe = int(opp_spe)
                except (ValueError, TypeError):
                    opp_spe = 0
            opp_skills = opp.get("skills", [])

            total_threat = 0.0
            threatened_mine: List[Dict[str, Any]] = []

            for mine in my_team:
                my_types = mine.get("types", [])
                my_spe = (mine.get("stats", {}) or {}).get("SPE") or 0
                if isinstance(my_spe, str):
                    try:
                        my_spe = int(my_spe)
                    except (ValueError, TypeError):
                        my_spe = 0

                # How effective are opponent's types against mine?
                for tid in opp_types:
                    mult = self.chart.get_multiplier(tid, my_types)
                    if mult >= 2.0:
                        total_threat += 10.0 * mult
                        threatened_mine.append({
                            "name": mine.get("name", "?"),
                            "threat_type": "type_weakness",
                            "multiplier": mult,
                        })
                    elif mult > 1.0:
                        total_threat += 2.0 * mult

                # How effective are opponent's skills against mine?
                for skill in opp_skills:
                    skill_type = skill.get("type_id")
                    if skill_type is not None:
                        mult = self.chart.get_multiplier(skill_type, my_types)
                        if mult >= 2.0:
                            total_threat += 5.0

                # Speed advantage
                if opp_spe > my_spe and opp_spe > 0:
                    total_threat += min(5.0, (opp_spe - my_spe) / 20.0)

                # How vulnerable is opponent to my types?
                for tid in my_types:
                    mult = self.chart.get_multiplier(tid, opp_types)
                    if mult >= 2.0:
                        total_threat -= 5.0 * mult

            # Threat level
            if total_threat >= 30:
                level = "高"
            elif total_threat >= 15:
                level = "中"
            else:
                level = "低"

            threats.append({
                "name": opp.get("name", "?"),
                "types": [self.chart.type_name(t) for t in opp_types],
                "threat_score": round(total_threat, 1),
                "threat_level": level,
                "threatened_mine": threatened_mine[:5],
            })

        threats.sort(key=lambda x: x["threat_score"], reverse=True)
        return threats

    def suggest_target_order(self, opponent_team: List[Dict[str, Any]],
                             my_active: Dict[str, Any]) -> List[Dict[str, Any]]:
        """建议击杀顺序 — 优先击杀对我方当前精灵威胁最大的。"""
        my_types = my_active.get("types", [])
        my_skills = my_active.get("skills", [])

        scored = []
        for opp in opponent_team:
            opp_types = opp.get("types", [])
            opp_name = opp.get("name", "?")

            # How effectively can I hit this opponent?
            best_mult = 1.0
            best_skill = None
            for skill in my_skills:
                skill_type = skill.get("type_id")
                if skill_type is not None:
                    mult = self.chart.get_multiplier(skill_type, opp_types)
                    if mult > best_mult:
                        best_mult = mult
                        best_skill = skill.get("name", "?")

            # How threatening is this opponent to me?
            threat = 0.0
            for tid in opp_types:
                mult = self.chart.get_multiplier(tid, my_types)
                if mult >= 2.0:
                    threat += 5.0

            # Priority: high effectiveness + high threat
            priority = best_mult * 10.0 + threat

            scored.append({
                "name": opp_name,
                "types": [self.chart.type_name(t) for t in opp_types],
                "best_multiplier": best_mult,
                "best_skill": best_skill,
                "threat_to_me": round(threat, 1),
                "target_priority": round(priority, 1),
            })

        scored.sort(key=lambda x: x["target_priority"], reverse=True)
        return scored
