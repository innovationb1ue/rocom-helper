"""换宠建议纯逻辑 — 供 SwitchAdvisorHook 和单元测试复用。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.constants import OPCODE_ACTION_RESOLVE
from src.analysis.counter import CounterPicker
from src.analysis.pet_identity import same_battle_pet
from src.game.type_chart import TypeChart


def best_effectiveness(
    chart: TypeChart,
    attack_types: List[int],
    defend_types: List[int],
) -> float:
    """返回攻击属性列表对防守属性列表的最佳倍率。"""
    best = 1.0
    for attack_type in attack_types:
        eff = chart.get_multiplier(attack_type, defend_types)
        if eff > best:
            best = eff
    return best


def is_opponent_switch(opcode: int, entries: List[Dict[str, Any]]) -> bool:
    """判断 action_resolve entries 中是否包含对手换宠。"""
    if opcode != OPCODE_ACTION_RESOLVE:
        return False

    for entry in entries:
        if entry.get("kind") != "change_pet":
            continue
        side_val = entry.get("target_side", entry.get("actor_side"))
        if isinstance(side_val, str):
            if side_val != "我方":
                return True
            continue
        if side_val is not None and int(side_val) >= 401:
            return True
    return False


def find_best_counter(
    counter_picker: CounterPicker,
    my_pets: List[Dict[str, Any]],
    opp_pet: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """从存活我方宠物中找出最适合应对当前对手的原始宠物字典。"""
    opp_types = opp_pet.get("types", [])
    if not opp_types:
        return None

    living = [
        pet for pet in my_pets
        if pet.get("current_hp", 1) > 0 and not same_battle_pet(pet, opp_pet)
    ]
    if not living:
        return None

    norm_opp = {"types": opp_types}
    norm_living = [
        {
            "types": pet.get("types", []),
            "pet_id": pet.get("pet_id"),
            "name": pet.get("name"),
            "slot": pet.get("slot"),
            "side": pet.get("side"),
            "base_conf_id": pet.get("base_conf_id"),
            "battle_uid": pet.get("battle_uid"),
        }
        for pet in living
    ]
    counters = counter_picker.find_counters([norm_opp], norm_living, top_n=1)
    if not counters:
        return None

    counter = counters[0]
    for pet in living:
        if same_battle_pet(pet, counter):
            return pet
    return None


def build_switch_messages(
    chart: TypeChart,
    counter_picker: CounterPicker,
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    my_pets: List[Dict[str, Any]],
    opcode: int,
    entries: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """基于当前对位和对手换宠事件生成 UI 消息。"""
    opp_types = opp_active.get("types", [])
    my_types = my_active.get("types", [])
    if not opp_types:
        return []

    messages: List[Dict[str, str]] = []
    my_offensive = best_effectiveness(chart, my_types, opp_types)
    opp_offensive = best_effectiveness(chart, opp_types, my_types)

    if opp_offensive >= 2.0 and my_offensive <= 1.0:
        best_switch = find_best_counter(counter_picker, my_pets, opp_active)
        if best_switch:
            pet_name = best_switch.get("name", "未知")
            best_eff = best_effectiveness(chart, best_switch.get("types", []), opp_types)
            messages.append({
                "type": "bad_matchup",
                "message": (
                    f"当前对局不利（{opp_active.get('name', '对手')}克制我方），"
                    f"建议换上 {pet_name}（克制 x{best_eff}）"
                ),
            })

    if messages or not is_opponent_switch(opcode, entries):
        return messages

    best_switch = find_best_counter(counter_picker, my_pets, opp_active)
    if best_switch and not same_battle_pet(best_switch, my_active):
        pet_name = best_switch.get("name", "未知")
        best_eff = best_effectiveness(chart, best_switch.get("types", []), opp_types)
        if best_eff >= 2.0:
            messages.append({
                "type": "counter_switch",
                "message": (
                    f"对手换上了 {opp_active.get('name', '新精灵')}，"
                    f"建议换上 {pet_name} 进行克制（x{best_eff}）"
                ),
            })
    return messages


def prefer_switch_target(
    chart: TypeChart,
    counter_picker: CounterPicker,
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
    my_pets: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """不利对位时返回建议换上的宠物。"""
    opp_types = opp_active.get("types", [])
    my_types = my_active.get("types", [])
    if not opp_types:
        return None

    my_offensive = best_effectiveness(chart, my_types, opp_types)
    opp_offensive = best_effectiveness(chart, opp_types, my_types)
    if opp_offensive < 2.0 or my_offensive > 1.0:
        return None
    return find_best_counter(counter_picker, my_pets, opp_active)
