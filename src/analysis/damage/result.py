"""伤害计算结果模型和结果构造辅助。"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class DamageResult:
    skill_id: int
    skill_name: str
    power: int
    effective_power: int
    damage_type: int  # 2=物理, 3=特殊
    skill_element: int
    skill_element_name: str
    effectiveness: float
    effectiveness_label: str
    is_stab: bool
    expected_damage: int
    pct_hp: float  # 伤害占 defender 最大 HP 的百分比
    can_ko: bool
    energy_cost: int
    confidence: str  # "high" / "medium"
    hit_count: int = 1
    power_mult: float = 1.0
    weather_mult: float = 1.0
    damage_breakdown: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    # Backward-compatible properties — deterministic damage has no range
    @property
    def min_damage(self) -> int:
        return self.expected_damage

    @property
    def max_damage(self) -> int:
        return self.expected_damage

    @property
    def total_damage(self) -> int:
        return self.expected_damage * self.hit_count

    @property
    def total_min_damage(self) -> int:
        return self.total_damage

    @property
    def total_max_damage(self) -> int:
        return self.total_damage

    @property
    def pct_hp_range(self) -> Tuple[float, float]:
        return (self.pct_hp, self.pct_hp)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Add computed properties for backward compatibility
        d["min_damage"] = self.min_damage
        d["max_damage"] = self.max_damage
        d["total_damage"] = self.total_damage
        d["total_min_damage"] = self.total_min_damage
        d["total_max_damage"] = self.total_max_damage
        d["pct_hp_range"] = self.pct_hp_range
        return d


def damage_result_from_dict(data: Dict[str, Any]) -> DamageResult:
    """从兼容 payload 重建 DamageResult，忽略计算属性等额外字段。"""
    return DamageResult(**{
        key: value
        for key, value in data.items()
        if key in DamageResult.__dataclass_fields__
    })


def collect_derived_buffs(buff_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把嵌套 derived_buffs 展平成带父 buff 标识的列表。"""
    derived: List[Dict[str, Any]] = []
    for buff in buff_list or []:
        if not isinstance(buff, dict):
            continue
        parent = {
            "id": buff.get("id"),
            "name": buff.get("name"),
        }
        for item in buff.get("derived_buffs") or []:
            if isinstance(item, dict):
                child = dict(item)
            else:
                child = {"id": item}
            child.setdefault("parent_buff_id", parent.get("id"))
            child.setdefault("parent_buff_name", parent.get("name"))
            derived.append({k: v for k, v in child.items() if v is not None})
    return derived


def base_hit_count(skill_meta: Dict[str, Any]) -> int:
    """从技能 desc 中提取基础连击数（如 '2连击' → 2）。"""
    desc = skill_meta.get("desc", "")
    m = re.search(r"(\d+)连击", desc)
    if m:
        return int(m.group(1))
    return 1


def skill_power(skill_meta: Dict[str, Any]) -> int:
    """从技能 meta 中取技能基础威力。"""
    dam_para = skill_meta.get("dam_para", [])
    if dam_para:
        return int(dam_para[0])
    return 0
