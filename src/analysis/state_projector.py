"""状态投影器 — 基于 entries 列表投影战斗状态的变化。

用于在 action_resolve 时生成“buff/能量/换宠已生效但 HP 未扣减”的投影状态，
使伤害预测反映实际 damage 发生前的完整上下文（如减伤 buff 是否被移除）。
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List

from src.analysis.projection.effects import project_effect_apply, project_effect_stage
from src.analysis.projection.field import project_weather_change
from src.analysis.projection.pets import project_change_pet
from src.analysis.projection.resources import (
    project_combo_skill_cast,
    project_energy,
    project_skill_cast,
)

EntryProjector = Callable[[Dict[str, Any], Dict[str, Any]], None]

ENTRY_PROJECTORS: Dict[str, EntryProjector] = {
    "effect_apply": project_effect_apply,
    "effect_stage": project_effect_stage,
    "energy": project_energy,
    "change_pet": project_change_pet,
    "combo_skill_cast": project_combo_skill_cast,
    "skill_cast": project_skill_cast,
    "weather_change": project_weather_change,
}


def project_state_after_entries(state: Dict[str, Any], entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """返回状态的浅拷贝，应用 entries 中的 buff/能量/换宠变化，但保留原始 HP。

    排除的 entries（不投影）：damage, defeat, heal —— 这些直接影响 HP，
    而我们希望在 projection 中保留 HP 用于伤害预测。
    """
    projected = copy.deepcopy(state)

    for entry in entries:
        projector = ENTRY_PROJECTORS.get(entry.get("kind"))
        if projector is not None:
            projector(projected, entry)

    return projected
