"""TacticalEngine 的行动枚举兼容方法。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.analysis.tactical import action_space


class TacticalActionMixin:
    """保留 TacticalEngine 旧私有入口，实际逻辑委托给 action_space。"""

    def _enumerate_our_actions(
        self, my_active: Dict[str, Any], my_pets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return action_space.enumerate_our_actions(my_active, my_pets)

    @staticmethod
    def _skills_from_pool(pet: Dict[str, Any]) -> List[Dict[str, Any]]:
        return action_space.skills_from_pool(pet)
