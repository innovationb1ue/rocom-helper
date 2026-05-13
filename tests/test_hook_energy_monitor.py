"""EnergyMonitorHook 测试 — 能量状态监控和预测。"""
from __future__ import annotations

import pytest

from src.analysis.hook_registry import HookContext, HookTrigger
from src.analysis.hooks.energy_monitor import EnergyMonitorHook


def _ctx(entries=None, opcode=0x1324, **overrides):
    defaults = {
        "opcode": opcode,
        "detail": {"entries": entries or []},
        "state": {
            "round": 1,
            "my_active": {
                "name": "火龙",
                "energy": 5,
                "equipped_skills": [
                    {"skill_id": 1, "skill_name": "火焰冲击", "skill_damage_type": 2, "cost_energy": 3},
                    {"skill_id": 2, "skill_name": "火花", "skill_damage_type": 2, "cost_energy": 2},
                ],
            },
            "opp_active": {"name": "水龟", "energy": 5},
        },
        "round_num": 1,
    }
    defaults.update(overrides)
    if entries is not None:
        defaults["detail"]["entries"] = entries
    return HookContext(**defaults)


@pytest.fixture
def hook():
    return EnergyMonitorHook()


class TestMyEnergy:
    def test_no_advice_at_full_energy(self, hook):
        result = hook.process(_ctx())
        assert result is None

    def test_warns_low_energy(self, hook):
        state = {
            "round": 3,
            "my_active": {
                "name": "火龙",
                "energy": 2,
                "equipped_skills": [
                    {"skill_id": 1, "skill_damage_type": 2, "cost_energy": 3},
                ],
            },
            "opp_active": {"name": "水龟", "energy": 5},
        }
        result = hook.process(_ctx(state=state))
        assert result is not None
        assert any("能量" in m["message"] for m in result.messages)

    def test_critical_when_starved(self, hook):
        state = {
            "round": 5,
            "my_active": {
                "name": "火龙",
                "energy": 1,
                "equipped_skills": [
                    {"skill_id": 1, "skill_damage_type": 2, "cost_energy": 3},
                    {"skill_id": 2, "skill_damage_type": 2, "cost_energy": 2},
                ],
            },
            "opp_active": {"name": "水龟", "energy": 5},
        }
        result = hook.process(_ctx(state=state))
        assert result is not None
        assert result.priority == 1
        assert any("无法" in m["message"] for m in result.messages)

    def test_no_advice_without_active(self, hook):
        result = hook.process(_ctx(state={"round": 1}))
        assert result is None


class TestOpponentEnergy:
    def test_detects_opp_energy_drop(self, hook):
        hook._opp_energy_log.append({"round": 1, "energy": 5})
        state = {
            "round": 2,
            "my_active": {"name": "火龙", "energy": 5, "equipped_skills": []},
            "opp_active": {"name": "水龟", "energy": 2},
        }
        result = hook.process(_ctx(state=state))
        assert result is not None
        assert any("对手" in m["message"] and "能量" in m["message"] for m in result.messages)


class TestLifecycle:
    def test_reset_clears_logs(self, hook):
        hook._my_energy_log.append({"round": 1, "energy": 5})
        hook._opp_energy_log.append({"round": 1, "energy": 5})
        hook.reset()
        assert hook._my_energy_log == []
        assert hook._opp_energy_log == []

    def test_battle_enter_resets(self, hook):
        hook._my_energy_log.append({"round": 1, "energy": 5})
        hook.on_battle_enter(_ctx(opcode=0x1316))
        assert hook._my_energy_log == []
