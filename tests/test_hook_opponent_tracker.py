"""OpponentTrackerHook 测试 — 对手技能追踪和换宠模式识别。"""
from __future__ import annotations

import pytest

from src.analysis.hook_registry import HookContext, HookTrigger
from src.analysis.hooks.opponent_tracker import OpponentTrackerHook


def _ctx(entries=None, opcode=0x1324, **overrides):
    defaults = {
        "opcode": opcode,
        "detail": {"entries": entries or []},
        "state": {
            "round": 1,
            "opp_active": {"name": "火龙", "types": [1], "hp_pct": 1.0},
            "my_active": {"name": "水龟", "types": [2]},
        },
        "round_num": 1,
        "entries": entries or [],
    }
    defaults.update(overrides)
    if entries is not None:
        defaults["detail"]["entries"] = entries
        defaults["entries"] = entries
    return HookContext(**defaults)


def _skill_cast(skill_name="火焰冲击", actor_side=401):
    return {
        "kind": "skill_cast",
        "skill_name": skill_name,
        "actor_side": actor_side,
    }


def _change_pet(new_name="水龙", target_side=401):
    return {
        "kind": "change_pet",
        "new_pet_name": new_name,
        "target_side": target_side,
        "actor_side": target_side,
    }


@pytest.fixture
def hook():
    return OpponentTrackerHook()


class TestSkillTracking:
    def test_no_advice_on_first_use(self, hook):
        ctx = _ctx(entries=[_skill_cast()])
        result = hook.process(ctx)
        assert result is None

    def test_no_advice_for_player_skill(self, hook):
        entries = [_skill_cast(actor_side=1)] * 3
        ctx = _ctx(entries=entries)
        result = hook.process(ctx)
        assert result is None

    def test_detects_preference_after_3_uses(self, hook):
        results = []
        for i in range(4):
            ctx = _ctx(entries=[_skill_cast("火焰冲击")], round_num=i + 1)
            hook.process(ctx)
            results.append(hook.process(ctx))
        # By 3rd or 4th use, preference should be detected
        detected = any(r is not None and any("偏好" in m["message"] for m in r.messages) for r in results)
        assert detected, "Should detect skill preference after 3+ uses"

    def test_tracks_multiple_skills(self, hook):
        for name in ["火焰冲击", "火焰冲击", "火花"]:
            ctx = _ctx(entries=[_skill_cast(name)], round_num=1)
            hook.process(ctx)
        counts = hook._opp_skill_counts.get("火龙", {})
        assert counts.get("火焰冲击") == 2
        assert counts.get("火花") == 1


class TestSwitchTracking:
    def test_logs_opp_switch(self, hook):
        ctx = _ctx(
            entries=[_change_pet("水龙")],
            state={
                "round": 2,
                "opp_active": {"name": "水龙", "types": [2], "hp_pct": 0.3},
                "my_active": {"name": "水龟", "types": [2]},
            },
        )
        hook.process(ctx)
        assert len(hook._opp_switch_log) == 1
        assert hook._opp_switch_log[0]["new_pet"] == "水龙"

    def test_detects_low_hp_switch_pattern(self, hook):
        for i in range(3):
            hook._opp_switch_log.append({
                "round": i + 1,
                "new_pet": f"pet_{i}",
                "prev_hp_pct": 0.2,
            })
        ctx = _ctx(entries=[_skill_cast()])
        result = hook.process(ctx)
        assert result is not None
        assert any("低HP" in m["message"] or "换宠" in m["message"] for m in result.messages)


class TestLifecycle:
    def test_reset_clears_state(self, hook):
        hook._opp_skill_counts["x"] = {"a": 1}
        hook._opp_switch_log.append({"round": 1})
        hook.reset()
        assert hook._opp_skill_counts == {}
        assert hook._opp_switch_log == []

    def test_battle_enter_resets(self, hook):
        hook._opp_skill_counts["x"] = {"a": 1}
        hook.on_battle_enter(_ctx(opcode=0x1316))
        assert hook._opp_skill_counts == {}
