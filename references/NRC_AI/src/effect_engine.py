"""
效果执行引擎 — 兼容层

原 3092 行单体文件已移至 src/engine/_monolith.py，
本文件 re-export 所有公共符号，保证外部代码零修改可用。

后续按模块拆分 _monolith.py 时，只需更改 __init__.py 的 import 来源。
"""

# Re-export everything that external code imports
from src.engine._monolith import (
    # Classes
    Ctx,
    EffectExecutor,
    # Registries
    _HANDLERS,
    _ABILITY_HANDLER_OVERRIDES,
    _apply_tag,
    # Utility functions (used by battle.py top-level import)
    _apply_permanent_mod,
    _adjust_cost_delta,
    _apply_buff,
    _apply_debuff,
    _clear_buffs,
    _clear_debuffs,
    _ability_name,
    _get_ability_name,
    _find_skill_index,
    _iter_flat_tags_static,
    _execute_agility_old,
    _apply_weather_damage,
    # Handlers (used by tests)
    _h_weather,
    # Filters
    _check_runtime_condition,
    _check_skill_filter,
)
