"""Damage calculation helper package."""

from src.analysis.damage.result import DamageResult
from src.analysis.damage.finalize import DamageFinalizeInput, finalize_damage_result
from src.analysis.damage.hook_pipeline import DamageHook, DamageHookPipeline, HookStage

__all__ = [
    "DamageFinalizeInput",
    "DamageHook",
    "DamageHookPipeline",
    "DamageResult",
    "HookStage",
    "finalize_damage_result",
]
