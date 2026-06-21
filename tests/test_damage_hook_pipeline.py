"""伤害 hook 管线测试。"""
from __future__ import annotations

import pytest

from src.analysis.damage.hook_pipeline import DamageHookPipeline


def test_hook_pipeline_initializes_all_stages():
    pipeline = DamageHookPipeline()

    assert set(pipeline.hooks) == {"pre_power", "post_base", "pre_final", "post_calc"}
    assert all(stage_hooks == [] for stage_hooks in pipeline.hooks.values())


def test_hook_pipeline_runs_hooks_in_registration_order():
    pipeline = DamageHookPipeline()
    calls = []

    def first(ctx):
        calls.append("first")
        return {**ctx, "power": ctx["power"] + 10}

    def second(ctx):
        calls.append("second")
        return {**ctx, "power": ctx["power"] * 2}

    pipeline.register("pre_power", first)
    pipeline.register("pre_power", second)

    assert pipeline.run("pre_power", {"power": 5}) == {"power": 30}
    assert calls == ["first", "second"]


def test_hook_pipeline_clear_removes_registered_hooks():
    pipeline = DamageHookPipeline()
    pipeline.register("post_calc", lambda ctx: ctx)

    pipeline.clear()

    assert pipeline.hooks["post_calc"] == []


def test_hook_pipeline_rejects_unknown_stage():
    pipeline = DamageHookPipeline()

    with pytest.raises(ValueError):
        pipeline.register("invalid", lambda ctx: ctx)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        pipeline.run("invalid", {})  # type: ignore[arg-type]
