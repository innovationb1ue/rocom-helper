"""洛克王国伤害计算器 — 基于属性克制、STAB、攻防属性的伤害预测。"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.data.loader import get_skill_meta, get_skill_name, get_wiki_pet_stats
from src.game.type_chart import TypeChart


@dataclass
class DamageResult:
    skill_id: int
    skill_name: str
    power: int
    damage_type: int  # 2=物理, 3=特殊
    skill_element: int
    skill_element_name: str
    effectiveness: float
    effectiveness_label: str
    is_stab: bool
    min_damage: int
    max_damage: int
    pct_hp_range: Tuple[float, float]
    can_ko: bool
    energy_cost: int
    confidence: str  # "high" / "medium" / "low"
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 属性名到 stat name 的映射
_ATK_STAT = {2: "ATK", 3: "SPA"}  # damage_type → 攻击属性
_DEF_STAT = {2: "DEF", 3: "SPD"}  # damage_type → 防御属性

# 随机因子范围 (217/255 ≈ 0.85, 255/255 = 1.0)
_RAND_MIN = 217 / 255
_RAND_MAX = 1.0

# STAB 倍率
_STAB_MULTIPLIER = 1.5

# Buff stage → stat multiplier  (stage -6 ~ +6)
# 每级约 +50% / -33%，参考宝可梦通用规则
_BUFF_STAGE_MULTIPLIERS = {
    -6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
    0: 1.0,
    1: 3/2, 2: 4/2, 3: 5/2, 4: 6/2, 5: 7/2, 6: 8/2,
}


class DamageCalculator:
    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self.chart = type_chart or TypeChart()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def calculate(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        skill_meta: Dict[str, Any],
    ) -> Optional[DamageResult]:
        """计算单个技能的伤害预测。返回 None 如果不是攻击技能。"""
        power = self._get_power(skill_meta)
        damage_type = skill_meta.get("damage_type", 0)
        if power <= 0 or damage_type not in (2, 3):
            return None

        skill_element = skill_meta.get("skill_dam_type", 0)
        level = attacker.get("level") or 100
        confidence = "high"
        warnings: List[str] = []

        # 获取攻防属性
        atk_name = _ATK_STAT[damage_type]
        def_name = _DEF_STAT[damage_type]
        atk_val = self._get_stat(attacker, atk_name)
        def_val = self._get_stat(defender, def_name)

        # 回退到 wiki 数据
        if atk_val is None:
            atk_val = self._get_wiki_stat(attacker, atk_name)
            if atk_val is not None:
                confidence = "medium"
                warnings.append("攻击属性来自 wiki 估算")
        if def_val is None:
            def_val = self._get_wiki_stat(defender, def_name)
            if def_val is not None:
                confidence = "medium"
                warnings.append("防御属性来自 wiki 估算")

        # 完全无数据时无法给出有意义的预测
        if atk_val is None or def_val is None:
            return None

        # Buff stage 修正
        atk_stage = self._get_stat_stage(attacker, atk_name)
        def_stage = self._get_stat_stage(defender, def_name)
        atk_val = int(atk_val * _BUFF_STAGE_MULTIPLIERS.get(atk_stage, 1.0))
        def_val = int(def_val * _BUFF_STAGE_MULTIPLIERS.get(def_stage, 1.0))
        if atk_stage != 0:
            warnings.append(f"攻击方 {atk_name} stage {atk_stage:+d}")
        if def_stage != 0:
            warnings.append(f"防御方 {def_name} stage {def_stage:+d}")

        # 属性克制
        defender_types = defender.get("types", [])
        effectiveness = self.chart.get_multiplier(skill_element, defender_types)
        eff_label = self.chart.get_effectiveness_label(effectiveness)

        # STAB
        attacker_types = attacker.get("types", [])
        is_stab = skill_element in attacker_types

        # 基础伤害
        base = self._base_damage(level, power, atk_val, def_val)

        # 最终伤害范围
        stab_mult = _STAB_MULTIPLIER if is_stab else 1.0
        max_dmg = max(1, int(base * effectiveness * stab_mult * _RAND_MAX))
        min_dmg = max(1, int(base * effectiveness * stab_mult * _RAND_MIN))

        # HP 百分比
        defender_max_hp = defender.get("max_hp") or defender.get("current_hp") or 1
        pct_min = min_dmg / defender_max_hp
        pct_max = max_dmg / defender_max_hp
        can_ko = min_dmg >= (defender.get("current_hp") or 0)

        # 能耗
        energy_costs = skill_meta.get("energy_cost", [0])
        energy_cost = energy_costs[0] if energy_costs else 0
        if energy_cost > 0:
            attacker_energy = attacker.get("energy", 10)
            if attacker_energy < energy_cost:
                warnings.append(f"能量不足 (需要{energy_cost}, 当前{attacker_energy})")

        return DamageResult(
            skill_id=skill_meta.get("id", 0),
            skill_name=skill_meta.get("name", "?"),
            power=power,
            damage_type=damage_type,
            skill_element=skill_element,
            skill_element_name=self.chart.type_name(skill_element) if skill_element else "无属性",
            effectiveness=effectiveness,
            effectiveness_label=eff_label,
            is_stab=is_stab,
            min_damage=min_dmg,
            max_damage=max_dmg,
            pct_hp_range=(round(pct_min, 3), round(pct_max, 3)),
            can_ko=can_ko,
            energy_cost=energy_cost,
            confidence=confidence,
            warnings=warnings,
        )

    def calculate_all(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        skills: List[Dict[str, Any]],
    ) -> List[DamageResult]:
        """计算所有攻击技能的伤害预测，按最大伤害降序排列。"""
        results: List[DamageResult] = []
        for skill in skills:
            skill_id = skill.get("skill_id")
            if skill_id is None:
                continue
            meta = get_skill_meta(skill_id)
            if meta is None:
                continue
            result = self.calculate(attacker, defender, meta)
            if result is not None:
                results.append(result)
        results.sort(key=lambda r: r.max_damage, reverse=True)
        return results

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _base_damage(level: int, power: int, attack: int, defense: int) -> int:
        """基础伤害公式: floor((level*0.4 + 2) * power * A / D / 50 + 2)"""
        if defense <= 0:
            defense = 1
        return int(math.floor((level * 0.4 + 2) * power * attack / defense / 50 + 2))

    @staticmethod
    def _get_power(skill_meta: Dict[str, Any]) -> int:
        """从技能 meta 中取威力。"""
        dam_para = skill_meta.get("dam_para", [])
        if dam_para:
            return int(dam_para[0])
        return 0

    @staticmethod
    def _get_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
        """从抓包数据中提取属性值。"""
        stats = pet.get("stats", [])
        for s in stats:
            if s.get("name") == stat_name:
                total = s.get("total")
                if total is not None:
                    return int(total)
                calc = s.get("calc") or 0
                bonus = s.get("bonus") or 0
                return calc + bonus
        return None

    @staticmethod
    def _get_wiki_stat(pet: Dict[str, Any], stat_name: str) -> Optional[int]:
        """从 wiki 数据回退获取属性值。"""
        name = pet.get("name")
        if not name:
            return None
        wiki_stats = get_wiki_pet_stats(name)
        if wiki_stats and stat_name in wiki_stats:
            return int(wiki_stats[stat_name])
        return None

    @staticmethod
    def _get_stat_stage(pet: Dict[str, Any], stat_name: str) -> int:
        """从 pet 的 buffs 中提取指定属性的 stage 值，累加所有相关 buff 的 stage。"""
        total = 0
        for buff in pet.get("buffs", []):
            stage = buff.get("stage")
            if isinstance(stage, int) and stage != 0:
                # buff 的 name 或 id 关联到属性名（粗粒度：所有非零 stage 都计入）
                total += stage
        return max(-6, min(6, total))
