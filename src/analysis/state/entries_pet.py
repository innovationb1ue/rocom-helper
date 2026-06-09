"""Pet switching action-entry handlers."""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.pet_info import PetInfo
from src.analysis.pet_identity import refresh_battle_uid

def _handle_change_pet_entry(self, entry: Dict[str, Any]) -> None:
    battle_pet_id = entry.get("battle_pet_id")
    new_pet_name = entry.get("new_pet_name")
    new_pet_id = entry.get("new_pet_id")
    new_base_conf_id = entry.get("new_pet_base_conf_id")
    if battle_pet_id is None:
        return

    # 判断换宠发生在哪方。target_side 1-6/401-406 在不同对局中可能反转
    # （取决于谁是房主），所以优先用已知宠物列表交叉验证。
    is_opp = None

    # 1. 用 rest_pet_id（被换下的宠物）匹配已知列表
    rest_pet_id = entry.get("rest_pet_id")
    if rest_pet_id is not None:
        for pet in self.state["opp_pets"]:
            if pet.get("pet_id") == rest_pet_id or pet.get("base_conf_id") == rest_pet_id:
                is_opp = True
                break
        if is_opp is None:
            for pet in self.state["my_pets"]:
                if pet.get("pet_id") == rest_pet_id or pet.get("base_conf_id") == rest_pet_id:
                    is_opp = False
                    break

    # 2. 用 new_pet_id 匹配已知列表（换上的宠物可能已知）
    if is_opp is None and new_pet_id is not None and new_pet_id != 20000000:
        for pet in self.state["opp_pets"]:
            if pet.get("pet_id") == new_pet_id:
                is_opp = True
                break
        if is_opp is None:
            for pet in self.state["my_pets"]:
                if pet.get("pet_id") == new_pet_id:
                    is_opp = False
                    break

    # 3. 已知的 slot 映射
    if is_opp is None:
        bpid = int(battle_pet_id)
        if bpid in self._opponent_slots:
            is_opp = True
        elif bpid in self._player_slots:
            is_opp = False

    # 4. 用当前活跃宠物判断（换宠替换的是活跃宠物）
    if is_opp is None and rest_pet_id is not None:
        active = self.state.get("opp_active")
        if active and (active.get("pet_id") == rest_pet_id or active.get("base_conf_id") == rest_pet_id):
            is_opp = True
    if is_opp is None and rest_pet_id is not None:
        active = self.state.get("my_active")
        if active and (active.get("pet_id") == rest_pet_id or active.get("base_conf_id") == rest_pet_id):
            is_opp = False

    # 5. Fallback: target_side numeric range
    if is_opp is None:
        target_side = entry.get("target_side")
        if target_side is not None:
            is_opp = int(target_side) >= 401

    # 6. Final fallback: battle_pet_id range
    if is_opp is None:
        bpid = int(battle_pet_id)
        is_opp = bpid >= 401

    # Record slot mapping
    bpid = int(battle_pet_id)
    if is_opp:
        self._opponent_slots.add(bpid)
    else:
        self._player_slots.add(bpid)

    pet_list = self.state["opp_pets"] if is_opp else self.state["my_pets"]
    active_key = "opp_active" if is_opp else "my_active"
    active = self.state[active_key]
    if active is not None:
        entry["_prev_active_name"] = active.get("name", "?")
    matched = None
    # 优先用 base_conf_id 匹配（始终可用，即使 pet_id=20000000）
    if new_base_conf_id is not None:
        for pet in pet_list:
            if pet.get("base_conf_id") == new_base_conf_id:
                matched = pet
                break
    # 其次用 pet_id 匹配（对手可能在之前的 change_pet 中已更新真实 conf_id）
    if matched is None and new_pet_id is not None and new_pet_id != 20000000:
        for pet in pet_list:
            if pet.get("pet_id") == new_pet_id:
                matched = pet
                break
    # 名称匹配作为兜底
    if matched is None and new_pet_name:
        for pet in pet_list:
            if pet.get("name") == new_pet_name:
                matched = pet
                break
    # Match by slot position (player slots 1-6 map to index 0-5)
    if matched is None and not is_opp:
        idx = int(battle_pet_id) - 1
        if 0 <= idx < len(pet_list):
            matched = pet_list[idx]
    # Not found — create a new pet entry from extracted data
    if matched is None and new_pet_name:
        matched = PetInfo.from_change_pet(entry, battle_pet_id, is_opp).to_dict()
        pet_list.append(matched)
    if matched is not None:
        if matched.get("side") is None:
            matched["side"] = 401 if is_opp else 1
        if matched.get("slot") is None:
            matched["slot"] = battle_pet_id
        # 如果获得了真实的 conf_id，更新宠物记录（从 20000000 更新为真实值）
        if new_pet_id is not None and new_pet_id != 20000000:
            if matched.get("pet_id") == 20000000:
                matched["pet_id"] = new_pet_id
        # 同样更新 base_conf_id
        if new_base_conf_id is not None and matched.get("base_conf_id") is None:
            matched["base_conf_id"] = new_base_conf_id
        refresh_battle_uid(matched, side=401 if is_opp else 1)
        self.state[active_key] = matched
        self._bind_battle_side(battle_pet_id, matched, is_mine=not is_opp)
        target_side = entry.get("target_side")
        if target_side is not None:
            self._bind_battle_side(target_side, matched, is_mine=not is_opp)
        matched["buffs"] = []
        matched["combo_bonus"] = 0
        matched["poison_stacks"] = 0
        # 保留该宠物已曝光技能；换下再换上时不应丢失历史追踪
        matched.setdefault("used_skills", [])
        # 用 change_pet wrapper 中的丰富数据更新已匹配的宠物
        if matched.get("base_speed") is None:
            bs = entry.get("new_pet_battle_stats") or []
            if len(bs) >= 6 and bs[5]:
                matched["base_speed"] = bs[5]
        if entry.get("new_pet_current_hp") is not None and entry.get("new_pet_max_hp") is not None:
            matched["max_hp"] = entry["new_pet_max_hp"]
            self._apply_hp_update(
                matched,
                event_kind="change_pet",
                entry=entry,
                side=entry.get("target_side") or battle_pet_id,
                target_pet_id=matched.get("pet_id"),
                hp_result=entry["new_pet_current_hp"],
                source_hint="change_pet",
            )
        if entry.get("new_pet_energy") is not None:
            matched["energy"] = min(10, entry["new_pet_energy"])
        if entry.get("new_pet_passive_skill_id") is not None:
            matched["innate_skill_id"] = entry["new_pet_passive_skill_id"]
