"""内置分析钩子 — 默认注册集。"""
from __future__ import annotations

from typing import List

from src.analysis.hook_registry import AnalysisHook


def create_default_hooks() -> List[AnalysisHook]:
    from src.analysis.hooks.energy_monitor import EnergyMonitorHook
    from src.analysis.hooks.opponent_tracker import OpponentTrackerHook
    from src.analysis.hooks.switch_advisor import SwitchAdvisorHook

    return [
        OpponentTrackerHook(),
        SwitchAdvisorHook(),
        EnergyMonitorHook(),
    ]
