"""技能分类器测试。"""
from __future__ import annotations

import pytest

from src.analysis.skill_classifier import classify_skill_effect, is_heal_skill, is_stat_up_skill


def _make_skill_meta(skill_result=None, desc="", dam_para=None, damage_type=1):
    return {
        "skill_result": skill_result or [],
        "desc": desc,
        "dam_para": dam_para or [0],
        "damage_type": damage_type,
    }


class TestClassifySkillEffect:
    def test_empty_skill(self):
        meta = _make_skill_meta()
        tags = classify_skill_effect(meta)
        assert "other" in tags

    def test_desc_heal(self):
        meta = _make_skill_meta(desc="恢复自身30%生命值")
        tags = classify_skill_effect(meta)
        assert "heal" in tags

    def test_desc_shield(self):
        meta = _make_skill_meta(desc="获得护盾，抵挡伤害")
        tags = classify_skill_effect(meta)
        assert "shield" in tags

    def test_desc_speed(self):
        meta = _make_skill_meta(desc="速度提升")
        tags = classify_skill_effect(meta)
        assert "speed" in tags

    def test_is_heal_skill(self):
        meta = _make_skill_meta(desc="治疗队友")
        assert is_heal_skill(meta) is True

    def test_is_stat_up_skill(self):
        meta = _make_skill_meta(desc="攻击力强化")
        assert is_stat_up_skill(meta) is True
