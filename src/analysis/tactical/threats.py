"""战术威胁目标选择。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from src.analysis.tactical import switch_targets
from src.analysis.threat import ThreatAssessor
from src.game.type_chart import TypeChart


class TargetOrderAssessor(Protocol):
    def suggest_target_order(
        self,
        opponent_team: List[Dict[str, Any]],
        my_active: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        ...


def top_threat_name(
    opp_pets: List[Dict[str, Any]],
    my_active: Dict[str, Any],
    *,
    chart: TypeChart,
    assessor: Optional[TargetOrderAssessor] = None,
) -> Optional[str]:
    """返回当前应优先压制的对手宠物名称。"""
    if not opp_pets:
        return None

    norm_my_active = switch_targets.normalize_pet_for_analysis(my_active)
    threat_assessor = assessor or ThreatAssessor(chart)
    target_order = threat_assessor.suggest_target_order(opp_pets, norm_my_active)
    if not target_order:
        return None
    return target_order[0].get("name")
