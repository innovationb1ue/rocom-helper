"""SwitchAdvisorHook 测试 — 换宠建议基于属性克制。"""
from __future__ import annotations

import pytest

from src.analysis.hook_registry import HookContext, HookTrigger
from src.analysis.hooks.switch_advisor import SwitchAdvisorHook
from src.game.type_chart import TypeChart


def _ctx(entries=None, opcode=0x131A, **overrides):
    defaults = {
        "opcode": opcode,
        "detail": {"entries": entries or []},
        "state": {
            "round": 1,
            "my_active": {"pet_id": 1, "name": "草龟", "types": [3], "current_hp": 200},
            "opp_active": {"pet_id": 101, "name": "火龙", "types": [1], "current_hp": 300},
            "my_pets": [
                {"pet_id": 1, "name": "草龟", "types": [3], "current_hp": 200},
                {"pet_id": 2, "name": "水龟", "types": [2], "current_hp": 300},
            ],
        },
        "round_num": 1,
        "entries": entries or [],
    }
    defaults.update(overrides)
    if entries is not None:
        defaults["detail"]["entries"] = entries
        defaults["entries"] = entries
    return HookContext(**defaults)


@pytest.fixture
def hook():
    return SwitchAdvisorHook(TypeChart())


class TestBadMatchup:
    def test_suggests_switch_when_disadvantaged(self, hook):
        # Grass (3) vs Fire (1) — fire beats grass
        result = hook.process(_ctx())
        assert result is not None
        assert any("不利" in m["message"] for m in result.messages)

    def test_no_switch_when_advantaged(self, hook):
        # Water (2) vs Fire (1) — water beats fire
        state = {
            "round": 1,
            "my_active": {"pet_id": 2, "name": "水龟", "types": [2], "current_hp": 300},
            "opp_active": {"pet_id": 101, "name": "火龙", "types": [1], "current_hp": 300},
            "my_pets": [
                {"pet_id": 2, "name": "水龟", "types": [2], "current_hp": 300},
            ],
        }
        result = hook.process(_ctx(state=state))
        assert result is None

    def test_no_advice_without_pets(self, hook):
        result = hook.process(_ctx(state={"round": 1}))
        assert result is None


class TestOpponentSwitch:
    def test_suggests_counter_on_opp_switch(self, hook):
        entries = [{
            "kind": "change_pet",
            "new_pet_name": "火龙",
            "new_pet_types": [1],
            "target_side": 401,
            "actor_side": 401,
        }]
        state = {
            "round": 2,
            "my_active": {"pet_id": 1, "name": "草龟", "types": [3], "current_hp": 200},
            "opp_active": {"pet_id": 101, "name": "火龙", "types": [1], "current_hp": 300},
            "my_pets": [
                {"pet_id": 1, "name": "草龟", "types": [3], "current_hp": 200},
                {"pet_id": 2, "name": "水龟", "types": [2], "current_hp": 300},
            ],
        }
        result = hook.process(_ctx(entries=entries, opcode=0x1324, state=state))
        assert result is not None
        assert result.hook_id == "switch_advisor"


class TestPriority:
    def test_switch_advice_is_important(self, hook):
        result = hook.process(_ctx())
        if result:
            assert result.priority == 1
