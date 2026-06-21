"""战术推荐置信度评估。"""
from __future__ import annotations

from typing import Any, Dict


def assess_confidence(opp_active: Dict[str, Any]) -> str:
    """评估推荐的置信度。"""
    equipped = opp_active.get("equipped_skills") or opp_active.get("skills") or []
    if equipped:
        return "high"
    used = opp_active.get("used_skills") or []
    if len(used) >= 3:
        return "high"
    if used:
        return "medium"
    return "low"
