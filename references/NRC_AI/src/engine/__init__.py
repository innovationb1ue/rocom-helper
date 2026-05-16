"""
效果执行引擎子包

原 effect_engine.py (3092行) 拆分为子包结构。
当前阶段: _monolith.py 持有全部代码，后续逐步拆分到子模块。

模块规划:
  _monolith.py     — 完整原始代码（过渡期）
  ctx.py           — Ctx 执行上下文 + 辅助函数（已就绪）
  filters.py       — 条件过滤（已就绪）
  handlers_*.py    — 按分类拆分的 handler（待拆）
  registry.py      — 注册表 + _apply_tag（待拆）
  executor.py      — EffectExecutor 类（待拆）
"""

from src.engine._monolith import (
    Ctx,
    EffectExecutor,
    _HANDLERS,
    _ABILITY_HANDLER_OVERRIDES,
    _apply_tag,
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
    _h_weather,
    _check_runtime_condition,
    _check_skill_filter,
)

__all__ = [
    "Ctx",
    "EffectExecutor",
    "_HANDLERS",
    "_ABILITY_HANDLER_OVERRIDES",
    "_apply_tag",
    "_apply_buff",
    "_apply_debuff",
    "_clear_buffs",
    "_clear_debuffs",
    "_ability_name",
    "_get_ability_name",
    "_find_skill_index",
    "_adjust_cost_delta",
    "_iter_flat_tags_static",
    "_apply_permanent_mod",
    "_execute_agility_old",
    "_apply_weather_damage",
    "_check_runtime_condition",
    "_check_skill_filter",
    "_h_weather",
]
