"""状态投影器测试 — 验证 action_resolve 时的 buff/能量/换宠投影。"""
from __future__ import annotations

import pytest

from src.analysis.state_projector import project_state_after_entries


def _make_state(my_active=None, opp_active=None, my_pets=None, opp_pets=None, weather=None):
    return {
        "my_active": my_active or {"buffs": [], "energy": 5, "current_hp": 100, "max_hp": 100},
        "opp_active": opp_active or {"buffs": [], "energy": 5, "current_hp": 100, "max_hp": 100},
        "my_pets": my_pets or [],
        "opp_pets": opp_pets or [],
        "weather": weather or {"id": None, "name": None},
    }


class TestProjectBuffChanges:
    def test_reduction_buff_removed_mid_turn(self):
        """减伤 buff 在 action_resolve 中被移除（stage=3），投影后不应再存在。"""
        state = _make_state(
            opp_active={
                "buffs": [{"id": 20030370, "stage": 1, "name": "减伤"}],
                "energy": 5,
                "current_hp": 100,
                "max_hp": 100,
            }
        )
        entries = [
            {"kind": "effect_stage", "actor_side": 401, "effect_id": 20030370, "effect_stage": 3},
        ]
        projected = project_state_after_entries(state, entries)
        opp = projected["opp_active"]
        assert len(opp["buffs"]) == 0

    def test_buff_stage_updated(self):
        """buff stage 更新应正确投影。"""
        state = _make_state(
            my_active={
                "buffs": [{"id": 21080150, "stage": 1, "name": "连击"}],
                "energy": 5,
                "current_hp": 100,
                "max_hp": 100,
            }
        )
        entries = [
            {"kind": "effect_stage", "actor_side": 1, "effect_id": 21080150, "effect_stage": 2},
        ]
        projected = project_state_after_entries(state, entries)
        my = projected["my_active"]
        assert my["buffs"][0]["stage"] == 2

    def test_new_buff_applied(self):
        """新 buff 被添加应投影到状态中。"""
        state = _make_state(
            opp_active={"buffs": [], "energy": 5, "current_hp": 100, "max_hp": 100}
        )
        entries = [
            {"kind": "effect_apply", "target_side": 401, "effect_id": 20030370, "effect_stage": 1, "effect_name": "减伤"},
        ]
        projected = project_state_after_entries(state, entries)
        opp = projected["opp_active"]
        assert len(opp["buffs"]) == 1
        assert opp["buffs"][0]["id"] == 20030370

    def test_new_stat_buff_has_modifier_summary(self):
        """属性 buff 投影后应带确定数值。"""
        state = _make_state(
            my_active={"buffs": [], "energy": 5, "current_hp": 100, "max_hp": 100}
        )
        entries = [
            {"kind": "effect_apply", "target_side": 1, "effect_id": 20010010, "effect_stage": 1, "effect_name": "物攻等级提升"},
        ]
        projected = project_state_after_entries(state, entries)
        buff = projected["my_active"]["buffs"][0]
        assert buff["modifiers"] == {"atk_up": 0.1}
        assert buff["modifier_summary"] == ["物攻 +10%"]

    def test_stat_buff_stage_update_recomputes_summary(self):
        """属性 buff stage 更新后数值摘要同步变化。"""
        state = _make_state(
            my_active={
                "buffs": [{"id": 20010010, "stage": 1, "name": "物攻等级提升"}],
                "energy": 5,
                "current_hp": 100,
                "max_hp": 100,
            }
        )
        entries = [
            {"kind": "effect_stage", "actor_side": 1, "effect_id": 20010010, "effect_stage": 2},
        ]
        projected = project_state_after_entries(state, entries)
        buff = projected["my_active"]["buffs"][0]
        assert buff["modifiers"] == {"atk_up": 0.2}
        assert buff["modifier_summary"] == ["物攻 +20%"]

    def test_hp_unchanged_by_damage(self):
        """damage entry 不应修改投影状态的 HP。"""
        state = _make_state(
            opp_active={"buffs": [], "energy": 5, "current_hp": 100, "max_hp": 100}
        )
        entries = [
            {"kind": "damage", "damage_target_side": 401, "damage": 50, "target_hp_after": 50},
        ]
        projected = project_state_after_entries(state, entries)
        assert projected["opp_active"]["current_hp"] == 100

    def test_energy_change_projected(self):
        """energy entry 应正确投影能量变化。"""
        state = _make_state(
            my_active={"buffs": [], "energy": 3, "current_hp": 100, "max_hp": 100}
        )
        entries = [
            {"kind": "energy", "target_side": 1, "energy_after": 6},
        ]
        projected = project_state_after_entries(state, entries)
        assert projected["my_active"]["energy"] == 6

    def test_combo_skill_cast_projected(self):
        """combo_skill_cast 应正确投影 combo_bonus。"""
        state = _make_state(
            my_active={"buffs": [], "energy": 5, "current_hp": 100, "max_hp": 100, "combo_bonus": 0}
        )
        entries = [
            {"kind": "combo_skill_cast", "actor_side": 1, "combo_count": 3},
        ]
        projected = project_state_after_entries(state, entries)
        assert projected["my_active"]["combo_bonus"] == 3

    def test_skill_cast_records_used_and_energy(self):
        """skill_cast 应记录使用技能并更新能量。"""
        state = _make_state(
            my_active={"buffs": [], "energy": 5, "current_hp": 100, "max_hp": 100, "used_skills": []}
        )
        entries = [
            {"kind": "skill_cast", "actor_side": 1, "skill_id": 7700001, "skill_name": "火焰冲击", "energy_after": 2},
        ]
        projected = project_state_after_entries(state, entries)
        assert projected["my_active"]["energy"] == 2
        assert len(projected["my_active"]["used_skills"]) == 1
        assert projected["my_active"]["used_skills"][0]["skill_id"] == 7700001

    def test_weather_change_projected(self):
        """weather_change 应更新天气状态。"""
        state = _make_state()
        entries = [
            {"kind": "weather_change", "weather_id": 5, "weather_name": "雨天", "expire_round": 10},
        ]
        projected = project_state_after_entries(state, entries)
        assert projected["weather"]["id"] == 5
        assert projected["weather"]["name"] == "雨天"

    def test_multiple_entries_projected_in_order(self):
        """多个 entries 按顺序投影。"""
        state = _make_state(
            opp_active={
                "buffs": [{"id": 20030370, "stage": 1, "name": "减伤"}],
                "energy": 5,
                "current_hp": 100,
                "max_hp": 100,
            }
        )
        entries = [
            {"kind": "effect_stage", "actor_side": 401, "effect_id": 20030370, "effect_stage": 3},
            {"kind": "energy", "target_side": 401, "energy_after": 8},
            {"kind": "damage", "damage_target_side": 401, "damage": 30, "target_hp_after": 70},
        ]
        projected = project_state_after_entries(state, entries)
        opp = projected["opp_active"]
        assert len(opp["buffs"]) == 0  # buff 被移除
        assert opp["energy"] == 8      # 能量更新
        assert opp["current_hp"] == 100  # HP 未变（damage 被排除）
