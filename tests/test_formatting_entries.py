"""动作 entry 格式化子模块测试。"""
from __future__ import annotations

from src.analysis.formatting.entries_combat import format_damage, format_defeat, format_skill_cast
from src.analysis.formatting.entries_effects import format_buff_trigger, format_effect_apply
from src.analysis.formatting.entries_misc import (
    format_cmd_failed,
    format_pvp_perform_marker,
    format_weather_change,
)
from src.analysis.formatting.entries_pet import format_change_model, format_change_pet, format_supply_pet
from src.analysis.formatting.entries_resources import format_energy, format_heal, format_use_item
from src.analysis.formatting.entry_dispatch import ENTRY_FORMATTERS, format_action_entry


def _state():
    return {
        "my_pets": [
            {"slot": 1, "pet_id": 100, "name": "火龙"},
            {"slot": 2, "pet_id": 101, "name": "草苗"},
        ],
        "opp_pets": [
            {"slot": 401, "pet_id": 200, "name": "水龟"},
            {"slot": 402, "pet_id": 201, "name": "电鼠"},
        ],
    }


def test_combat_entry_formatters_keep_legacy_summaries():
    skill = format_skill_cast(
        {"actor_side": 1, "skill_name": "毒囊", "energy_delta": -2, "energy_after": 8},
        _state(),
    )
    damage = format_damage(
        {"damage_target_side": 401, "damage": 32, "target_hp_after": 366, "skill_name": "毒囊"},
        _state(),
    )
    defeat = format_defeat({"actor_side": 1, "target_side": 401}, _state())

    assert skill.summary == "我方 使用 毒囊 (消耗2能量, 剩余8)"
    assert damage.summary == "敌方(水龟) 受到 32 伤害 (HP→366) [毒囊]"
    assert damage.detail["hp_after"] == 366
    assert damage.detail["target_side"] == "敌方"
    assert damage.detail["target_name"] == "水龟"
    assert "水龟" in defeat.summary
    assert defeat.detail["defeated_side"] == "敌方"
    assert defeat.detail["defeated_name"] == "水龟"


def test_effect_entry_formatters_enrich_modifiers_and_bases():
    effect = format_effect_apply(
        {
            "actor_side": 1,
            "target_side": 401,
            "effect_id": 20010020,
            "effect_name": "魔攻等级提升",
            "effect_stage": 1,
        },
        _state(),
    )
    trigger = format_buff_trigger(
        {"actor_side": 401, "target_side": 401, "effect_name": "光", "buffbase_ids": [2017088]},
        _state(),
    )

    assert "魔攻 +10%" in effect.summary
    assert effect.detail["modifier_summary"] == ["魔攻 +10%"]
    assert "base=2017088" in trigger.summary


def test_resource_entry_formatters_cover_hp_energy_and_items():
    heal = format_heal({"actor_side": 1, "target_side": 1, "hp_after": 280}, _state())
    energy = format_energy({"actor_side": 0, "target_side": 1, "energy_delta": 1, "energy_after": 10}, _state())
    item = format_use_item({"item_id": 123, "target_id": 401}, _state())

    assert heal.color == "green"
    assert "after=10" in energy.summary
    assert item.summary == "使用道具: item=123 target=敌方"


def test_pet_entry_formatters_resolve_names_from_state():
    change = format_change_pet({"battle_pet_id": 2, "_prev_active_name": "火龙"}, _state())
    model = format_change_model({"actor_side": 1, "model_pet_name": "新模型"}, _state())
    supply = format_supply_pet({"supply_pets": [{"pet_id": 1}, {"pet_id": 2}]}, _state())

    assert change.summary == "我方 换宠: 火龙 → 草苗"
    assert "火龙 -> 新模型" in model.summary
    assert supply.detail["supply_count"] == 2


def test_misc_entry_formatters_keep_system_event_shapes():
    weather = format_weather_change({"weather_name": "阴雨", "expire_round": 5, "skill_name": "天洪"}, _state())
    pvp = format_pvp_perform_marker({"pvp_type": 3}, _state())
    failed = format_cmd_failed({"failed_reason": 7}, _state())

    assert weather.summary == "天气变化: 阴雨 持续至回合5 (天洪)"
    assert pvp.kind == "pvp_perform"
    assert failed.color == "red"


def test_entry_dispatch_uses_registry_and_suppresses_internal_updates():
    assert ENTRY_FORMATTERS["damage"] is format_damage
    assert format_action_entry({"kind": "data_update"}, _state()) is None

    event = format_action_entry({"kind": "some_new_kind", "value": 1}, _state(), round_num=9)
    assert event is not None
    assert event.kind == "some_new_kind"
    assert event.round == 9
