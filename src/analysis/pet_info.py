"""宠物信息构造工厂 — 统一 battle_state.py 中 3 处重复的宠物字典构造。

PetInfo 是一个构造辅助类，不是运行时类型。通过 from_wrapper()/from_change_pet()
构造，再通过 to_dict() 转为可变字典，与所有下游代码完全兼容。
"""
from __future__ import annotations

from typing import Any, Dict, List


class PetInfo:
    """宠物战斗信息构造器。"""

    __slots__ = (
        "pet_id", "name", "types", "current_hp", "max_hp", "hp_pct",
        "energy", "buffs", "initial_buff_ids", "innate_skill_id",
        "level", "slot", "side", "stats", "skills", "equipped_skills",
        "base_id", "base_skill_pool", "combo_bonus", "poison_stacks",
        "used_skills",
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
        pet.energy = w.get("energy", default_energy)
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
        pet.recalc_hp_pct()
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
        pet.recalc_hp_pct()
        return pet
