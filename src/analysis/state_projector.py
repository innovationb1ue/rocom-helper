"""状态投影器 — 基于 entries 列表投影战斗状态的变化。

用于在 action_resolve 时生成“buff/能量/换宠已生效但 HP 未扣减”的投影状态，
使伤害预测反映实际 damage 发生前的完整上下文（如减伤 buff 是否被移除）。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from src.analysis.battle_state import POISON_BUFF_IDS
from src.analysis.pet_identity import refresh_battle_uid


def project_state_after_entries(state: Dict[str, Any], entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """返回状态的浅拷贝，应用 entries 中的 buff/能量/换宠变化，但保留原始 HP。

    排除的 entries（不投影）：damage, defeat, heal —— 这些直接影响 HP，
    而我们希望在 projection 中保留 HP 用于伤害预测。
    """
    projected = copy.deepcopy(state)

    for entry in entries:
        kind = entry.get("kind")
        if kind == "effect_apply":
            _project_effect_apply(projected, entry)
        elif kind == "effect_stage":
            _project_effect_stage(projected, entry)
        elif kind == "energy":
            _project_energy(projected, entry)
        elif kind == "change_pet":
            _project_change_pet(projected, entry)
        elif kind == "combo_skill_cast":
            _project_combo_skill_cast(projected, entry)
        elif kind == "skill_cast":
            _project_skill_cast(projected, entry)
        elif kind == "weather_change":
            _project_weather_change(projected, entry)
        # 排除: damage, defeat, heal — 保留原始 HP

    return projected


def _get_active_for_side(state: Dict[str, Any], side_value: Any) -> Optional[Dict[str, Any]]:
    """根据 side 值获取对应的活跃宠物字典（复用 battle_state 逻辑）。"""
    if side_value is None:
        return None
    is_mine = False
    if isinstance(side_value, str):
        is_mine = side_value == "我方"
    else:
        v = int(side_value)
        is_mine = 1 <= v <= 6
    key = "my_active" if is_mine else "opp_active"
    return state.get(key)


def _project_effect_apply(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    target_side = entry.get("target_side")
    effect_id = entry.get("effect_id")
    if target_side is None or effect_id is None:
        return
    active = _get_active_for_side(state, target_side)
    if active is None:
        return
    buffs = active.setdefault("buffs", [])
    stage = entry.get("effect_stage")
    ename = entry.get("effect_name")
    # BuffChangeType: 0=NULL, 1=ADD, 2=CHANGE, 3=REMOVE
    if stage == 3:
        active["buffs"] = [b for b in buffs if b.get("id") != effect_id]
        return
    existing = next((b for b in buffs if b["id"] == effect_id), None)
    if existing:
        if stage is not None:
            existing["stage"] = stage
        existing["turns_applied"] = existing.get("turns_applied", 0) + 1
    else:
        buffs.append({
            "id": effect_id,
            "name": ename or str(effect_id),
            "stage": stage,
            "source_skill": (entry.get("related_skills") or [{}])[0].get("skill_name") if entry.get("related_skills") else None,
            "turns_applied": 1,
        })
    if effect_id in POISON_BUFF_IDS:
        active["poison_stacks"] = stage if stage is not None else active.get("poison_stacks", 0) + 1


def _project_effect_stage(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    actor_side = entry.get("actor_side")
    effect_id = entry.get("effect_id")
    new_stage = entry.get("effect_stage")
    if actor_side is None:
        return
    active = _get_active_for_side(state, actor_side)
    if active is not None:
        buffs = active.get("buffs", [])
        if new_stage == 3:
            active["buffs"] = [b for b in buffs if b.get("id") != effect_id]
            return
        existing = next((b for b in buffs if b.get("id") == effect_id), None)
        if existing and new_stage is not None:
            existing["stage"] = new_stage


def _project_energy(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    target_side = entry.get("target_side") or entry.get("actor_side")
    energy_after = entry.get("energy_after")
    energy_delta = entry.get("energy_delta")
    if target_side is None:
        return
    active = _get_active_for_side(state, target_side)
    if active is not None:
        if energy_after is not None:
            active["energy"] = min(10, energy_after)
        elif energy_delta is not None:
            active["energy"] = min(10, max(0, active.get("energy", 5) + energy_delta))


def _project_change_pet(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    """简化版换宠投影：仅更新 active 指针，不修改宠物列表 HP。"""
    battle_pet_id = entry.get("battle_pet_id")
    new_pet_name = entry.get("new_pet_name")
    new_pet_id = entry.get("new_pet_id")
    new_base_conf_id = entry.get("new_pet_base_conf_id")
    if battle_pet_id is None:
        return

    # 简化的 side 判断（同 battle_state 的 fallback）
    target_side = entry.get("target_side")
    is_opp = False
    if target_side is not None:
        is_opp = int(target_side) >= 401
    else:
        bpid = int(battle_pet_id)
        is_opp = bpid >= 401

    pet_list = state.get("opp_pets" if is_opp else "my_pets", [])
    active_key = "opp_active" if is_opp else "my_active"

    matched = None
    if new_base_conf_id is not None:
        for pet in pet_list:
            if pet.get("base_conf_id") == new_base_conf_id:
                matched = pet
                break
    if matched is None and new_pet_id is not None and new_pet_id != 20000000:
        for pet in pet_list:
            if pet.get("pet_id") == new_pet_id:
                matched = pet
                break
    if matched is None and new_pet_name:
        for pet in pet_list:
            if pet.get("name") == new_pet_name:
                matched = pet
                break
    if matched is None and not is_opp:
        idx = int(battle_pet_id) - 1
        if 0 <= idx < len(pet_list):
            matched = pet_list[idx]

    if matched is not None:
        if matched.get("side") is None:
            matched["side"] = 401 if is_opp else 1
        if matched.get("slot") is None:
            matched["slot"] = battle_pet_id
        refresh_battle_uid(matched, side=401 if is_opp else 1)
        state[active_key] = matched


def _project_combo_skill_cast(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    actor_side = entry.get("actor_side")
    combo_count = entry.get("combo_count")
    if actor_side is not None and combo_count is not None:
        active = _get_active_for_side(state, actor_side)
        if active is not None:
            active["combo_bonus"] = combo_count


def _project_skill_cast(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    actor_side = entry.get("actor_side", "")
    energy_delta = entry.get("energy_delta", 0)
    energy_after = entry.get("energy_after")
    active = _get_active_for_side(state, actor_side)
    if active is None:
        return
    skill_id = entry.get("skill_id")
    if skill_id is not None:
        used = active.setdefault("used_skills", [])
        if not any(s.get("skill_id") == skill_id for s in used):
            item = {"skill_id": skill_id}
            if entry.get("skill_name"):
                item["skill_name"] = entry["skill_name"]
            used.append(item)
    if energy_after is not None:
        active["energy"] = min(10, energy_after)
    else:
        active["energy"] = min(10, max(0, active.get("energy", 5) + energy_delta))


def _project_weather_change(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    weather_id = entry.get("weather_id")
    if weather_id is not None:
        state["weather"] = {
            "id": weather_id,
            "name": entry.get("weather_name"),
            "expire_round": entry.get("expire_round"),
        }
