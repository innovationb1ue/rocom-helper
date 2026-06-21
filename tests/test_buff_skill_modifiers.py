"""技能威力/连击 buff 修正查询测试。"""
from __future__ import annotations

from src.data import buff_modifiers
from src.data.buff_skill_modifiers import get_buff_hit_count_modifiers, get_buff_power_modifiers


def test_power_modifier_counts_repeated_flat_children():
    assert get_buff_power_modifiers([{"id": 20171870, "name": "普通加威力"}]) == {
        "flat": 20.0,
        "sources": [20230440, 20230440],
    }


def test_power_modifier_filters_element_scope():
    buff = [{"id": 20171870, "name": "普通加威力"}]

    assert get_buff_power_modifiers(buff, skill_element=17) == {}
    assert get_buff_power_modifiers(buff, skill_element=0)["flat"] == 20.0


def test_hit_count_modifier_requires_multi_hit_when_root_is_multi_hit_only():
    buff = [{"id": 20172000, "name": "翼加连击"}]

    assert get_buff_hit_count_modifiers(buff, base_hit_count=1) == {}
    assert get_buff_hit_count_modifiers(buff, base_hit_count=2) == {
        "flat": 1.0,
        "sources": [20450050],
    }


def test_source_skill_must_match_when_present():
    buff = [{"id": 20171870, "name": "普通加威力", "source_skill": "折射"}]

    assert get_buff_power_modifiers(buff)["flat"] == 20.0
    assert get_buff_power_modifiers(buff, skill_name="毒囊") == {}
    assert get_buff_power_modifiers(buff, skill_name="折射")["flat"] == 20.0


def test_source_skill_hit_modifier_requires_current_skill_name():
    buff = [{"id": 20172000, "name": "翼加连击", "source_skill": "折射"}]

    assert get_buff_hit_count_modifiers(buff, base_hit_count=2)["flat"] == 1.0
    assert get_buff_hit_count_modifiers(buff, skill_name="追打", base_hit_count=2) == {}
    assert get_buff_hit_count_modifiers(buff, skill_name="折射", base_hit_count=2) == {}


def test_reflect_ignores_hit_count_modifiers_even_when_multi_hit():
    buff = [{"id": 20172000, "name": "翼加连击"}]

    assert get_buff_hit_count_modifiers(buff, skill_name="折射", base_hit_count=4) == {}


def test_response_chase_hit_modifier_does_not_apply_to_normal_chase():
    buff = [{"id": 20172000, "name": "翼加连击", "source_skill": "应对！追打"}]

    assert get_buff_hit_count_modifiers(buff, skill_name="追打", base_hit_count=4) == {}
    assert get_buff_hit_count_modifiers(buff, skill_name="应对！追打", base_hit_count=4)["flat"] == 1.0


def test_reflect_derived_hit_modifier_requires_matched_runtime_target_when_requested():
    buff = [{"id": 20172000, "name": "翼加连击", "parent_buff_name": "折射"}]

    assert get_buff_hit_count_modifiers(buff, skill_name="追打", base_hit_count=4)["flat"] == 1.0
    assert get_buff_hit_count_modifiers(
        buff,
        skill_name="追打",
        base_hit_count=4,
        allow_reflect_derived_hit=False,
    ) == {}


def test_buff_modifiers_keeps_compatibility_reexports():
    assert buff_modifiers.get_buff_power_modifiers is get_buff_power_modifiers
    assert buff_modifiers.get_buff_hit_count_modifiers is get_buff_hit_count_modifiers
