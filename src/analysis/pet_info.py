"""宠物信息构造工厂 — 统一 battle_state.py 中 3 处重复的宠物字典构造。

PetInfo 是一个构造辅助类，不是运行时类型。通过 from_wrapper()/from_change_pet()
构造，再通过 to_dict() 转为可变字典，与所有下游代码完全兼容。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PetInfo:
    """宠物战斗信息构造器。"""

    __slots__ = (
        "pet_id", "name", "types", "current_hp", "max_hp", "hp_pct",
        "energy", "buffs", "initial_buff_ids", "innate_skill_id",
        "level", "slot", "side", "stats", "skills", "equipped_skills",
        "base_id", "base_skill_pool", "combo_bonus", "poison_stacks",
        "used_skills", "base_speed",
    )

    def __init__(self) -> None:
        self.pet_id: Any = None
        self.name: str = "?"
        self.types: List[int] = []
        self.current_hp: int = 0
        self.max_hp: int = 0
        self.hp_pct: float = 1.0
        self.energy: int = 5
        self.buffs: List[Dict[str, Any]] = []
        self.initial_buff_ids: List[int] = []
        self.innate_skill_id: Any = None
        self.level: Any = None
        self.slot: Any = None
        self.side: Any = None
        self.stats: List[Dict[str, Any]] = []
        self.skills: List[Dict[str, Any]] = []
        self.equipped_skills: List[Dict[str, Any]] = []
        self.base_id: Any = None
        self.base_skill_pool: Any = None
        self.combo_bonus: int = 0
        self.poison_stacks: int = 0
        self.used_skills: List[Dict[str, Any]] = []
        self.base_speed: Optional[int] = None

    def recalc_hp_pct(self) -> None:
        if self.max_hp > 0:
            self.hp_pct = self.current_hp / self.max_hp
        else:
            self.hp_pct = 1.0 if self.current_hp > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pet_id": self.pet_id,
            "name": self.name,
            "types": self.types,
            "current_hp": self.current_hp,
            "max_hp": self.max_hp,
            "hp_pct": self.hp_pct,
            "energy": self.energy,
            "buffs": self.buffs,
            "initial_buff_ids": self.initial_buff_ids,
            "innate_skill_id": self.innate_skill_id,
            "level": self.level,
            "slot": self.slot,
            "side": self.side,
            "stats": self.stats,
            "skills": self.skills,
            "equipped_skills": self.equipped_skills,
            "base_id": self.base_id,
            "base_skill_pool": self.base_skill_pool,
            "combo_bonus": self.combo_bonus,
            "poison_stacks": self.poison_stacks,
            "used_skills": self.used_skills,
            "base_speed": self.base_speed,
        }

    @classmethod
    def from_wrapper(cls, w: Dict[str, Any], default_energy: int = 5) -> "PetInfo":
        """从协议 state wrapper 构造宠物信息。"""
        pet = cls()
        equipped = w.get("equipped_skills") or []
        initial_buffs = w.get("initial_buffs", [])
        pet.pet_id = w.get("pet_id") or w.get("pet_gid")
        pet.name = w.get("pet_name") or w.get("name", "?")
        pet.types = w.get("types", [])
        pet.current_hp = w.get("hp") or w.get("current_hp", 0)
        pet.max_hp = w.get("max_hp", 0)
        pet.energy = min(10, w.get("energy", default_energy))
        pet.buffs = list(initial_buffs)
        pet.initial_buff_ids = [b["id"] for b in initial_buffs if "id" in b]
        pet.innate_skill_id = w.get("passive_skill_id")
        pet.level = w.get("level")
        pet.slot = w.get("slot")
        pet.side = w.get("side")
        pet.stats = w.get("stats", [])
        pet.skills = w.get("skills", [])
        pet.equipped_skills = equipped
        pet.base_id = w.get("base_id")
        pet.base_skill_pool = w.get("base_skill_pool")
        # 从 battle_stats[5] 提取基础速度（含性格/个体/努力值，战斗中不变）
        battle_stats = w.get("battle_stats") or []
        if len(battle_stats) >= 6 and battle_stats[5] is not None and battle_stats[5] > 0:
            pet.base_speed = battle_stats[5]
        pet.recalc_hp_pct()
        logger.debug("PetInfo.from_wrapper: %s hp=%d/%d energy=%d skills=%d",
                     pet.name, pet.current_hp, pet.max_hp, pet.energy, len(equipped))
        return pet

    @classmethod
    def from_change_pet(
        cls,
        entry: Dict[str, Any],
        battle_pet_id: int,
        is_opp: bool,
    ) -> "PetInfo":
        """从 change_pet action entry 构造宠物信息（换宠时不在阵容中的新宠物）。"""
        pet = cls()
        pet.pet_id = entry.get("new_pet_id")
        pet.name = entry.get("new_pet_name", "?")
        pet.types = entry.get("new_pet_types", [])
        pet.side = 401 if is_opp else 1
        pet.slot = battle_pet_id
        pet.level = entry.get("new_pet_level")
        # 从 pet_state (BattleInsidePetInfo) 提取的丰富数据
        if entry.get("new_pet_current_hp") is not None:
            pet.current_hp = entry["new_pet_current_hp"]
        if entry.get("new_pet_max_hp") is not None:
            pet.max_hp = entry["new_pet_max_hp"]
        if entry.get("new_pet_energy") is not None:
            pet.energy = min(10, entry["new_pet_energy"])
        battle_stats = entry.get("new_pet_battle_stats") or []
        if len(battle_stats) >= 6 and battle_stats[5] is not None and battle_stats[5] > 0:
            pet.base_speed = battle_stats[5]
        if entry.get("new_pet_passive_skill_id") is not None:
            pet.innate_skill_id = entry["new_pet_passive_skill_id"]
        pet.recalc_hp_pct()
        logger.debug("PetInfo.from_change_pet: %s hp=%d/%d energy=%d opp=%s",
                     pet.name, pet.current_hp, pet.max_hp, pet.energy, is_opp)
        return pet
