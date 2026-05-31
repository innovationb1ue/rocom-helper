"""统一技能伤害预测服务。

该模块把 DamageCalculator 的公式结果包装成可解释、可校准、可对账的输出。
旧字段仍由调用方写回 SkillAnalysis；新增 prediction/explain/validation_hint 用于前端和回放校验。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.analysis.damage_calc import DamageCalculator, DamageResult
from src.analysis.innate_hooks import register_innate_hooks
from src.config import settings
from src.game.type_chart import TypeChart


_CALIBRATION_PATH = settings.config_dir / "damage_calibration.json"
_SPECIAL_RULES_PATH = settings.config_dir / "special_damage_rules.json"
_SERVER_POWER_RULES_PATH = settings.config_dir / "server_power_rules.json"


@dataclass(frozen=True)
class SpecialDamageRule:
    mode: str = ""
    element: Optional[int] = None
    hit_count: Optional[int] = None
    per_hit: Optional[int] = None
    source_sessions: tuple[str, ...] = ()
    notes: str = ""
    key: str = ""

    @property
    def is_present(self) -> bool:
        return bool(self.key and self.mode)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "mode": self.mode,
            "element": self.element,
            "hit_count": self.hit_count,
            "per_hit": self.per_hit,
            "source_sessions": list(self.source_sessions),
            "notes": self.notes,
            "applied": self.is_present and self.per_hit is not None and self.hit_count is not None,
        }


class SpecialDamageRuleStore:
    """读取特殊固定伤害规则。v1 只读，不自动学习。"""

    def __init__(self, path: Path = _SPECIAL_RULES_PATH) -> None:
        self.path = path
        self._data: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        if self._data is not None:
            return self._data
        if not self.path.exists():
            self._data = {"version": 1, "skills": {}}
            return self._data
        try:
            with self.path.open("r", encoding="utf-8-sig") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            data = {"version": 1, "skills": {}}
        self._data = data if isinstance(data, dict) else {"version": 1, "skills": {}}
        return self._data

    def get(self, skill_id: int) -> SpecialDamageRule:
        raw = self._load().get("skills", {}).get(str(skill_id))
        if not isinstance(raw, dict):
            return SpecialDamageRule()
        sessions = raw.get("source_sessions") or []
        return SpecialDamageRule(
            mode=str(raw.get("mode", "")),
            element=raw.get("element"),
            hit_count=raw.get("hit_count"),
            per_hit=raw.get("per_hit"),
            source_sessions=tuple(str(s) for s in sessions),
            notes=str(raw.get("notes", "")),
            key=str(skill_id),
        )


class ServerPowerRuleStore:
    """读取按技能启用的服务器威力规则。v1 只读。"""

    def __init__(self, path: Path = _SERVER_POWER_RULES_PATH) -> None:
        self.path = path
        self._data: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        if self._data is not None:
            return self._data
        if not self.path.exists():
            self._data = {"version": 1, "skills": {}}
            return self._data
        try:
            with self.path.open("r", encoding="utf-8-sig") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            data = {"version": 1, "skills": {}}
        self._data = data if isinstance(data, dict) else {"version": 1, "skills": {}}
        return self._data

    def rules(self) -> Dict[str, Any]:
        return self._load().get("skills", {})


@dataclass(frozen=True)
class DamageCalibration:
    multiplier: float = 1.0
    sample_count: int = 0
    mae: Optional[float] = None
    mape: Optional[float] = None
    source_sessions: tuple[str, ...] = ()
    notes: str = ""
    key: str = ""

    @property
    def is_present(self) -> bool:
        return bool(self.key)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "multiplier": self.multiplier,
            "sample_count": self.sample_count,
            "mae": self.mae,
            "mape": self.mape,
            "source_sessions": list(self.source_sessions),
            "notes": self.notes,
            "applied": self.is_present and self.multiplier != 1.0,
        }


class DamageCalibrationStore:
    """读取版本化伤害校准表。v1 只读，不自动写入。"""

    def __init__(self, path: Path = _CALIBRATION_PATH) -> None:
        self.path = path
        self._data: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        if self._data is not None:
            return self._data
        if not self.path.exists():
            self._data = {"version": 1, "skills": {}}
            return self._data
        try:
            with self.path.open("r", encoding="utf-8-sig") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            data = {"version": 1, "skills": {}}
        self._data = data if isinstance(data, dict) else {"version": 1, "skills": {}}
        return self._data

    def get(self, skill_id: int) -> DamageCalibration:
        raw = self._load().get("skills", {}).get(str(skill_id))
        if not isinstance(raw, dict):
            return DamageCalibration()
        sessions = raw.get("source_sessions") or []
        return DamageCalibration(
            multiplier=float(raw.get("multiplier", 1.0)),
            sample_count=int(raw.get("sample_count", 0)),
            mae=raw.get("mae"),
            mape=raw.get("mape"),
            source_sessions=tuple(str(s) for s in sessions),
            notes=str(raw.get("notes", "")),
            key=str(skill_id),
        )


class DamagePredictionService:
    """统一预测入口：公式计算、校准、解释和置信度标记。"""

    def __init__(
        self,
        type_chart: Optional[TypeChart] = None,
        *,
        calibration_store: Optional[DamageCalibrationStore] = None,
        special_rule_store: Optional[SpecialDamageRuleStore] = None,
        server_power_rule_store: Optional[ServerPowerRuleStore] = None,
        damage_calc: Optional[DamageCalculator] = None,
    ) -> None:
        self.chart = type_chart or TypeChart()
        self._damage_calc = damage_calc or DamageCalculator(self.chart)
        if damage_calc is None:
            register_innate_hooks(self._damage_calc)
        self._calibration_store = calibration_store or DamageCalibrationStore()
        self._special_rule_store = special_rule_store or SpecialDamageRuleStore()
        self._server_power_rule_store = server_power_rule_store or ServerPowerRuleStore()
        self._damage_calc.set_server_power_rules(self._server_power_rule_store.rules())

    def predict(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        skill_meta: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        dr = self._damage_calc.calculate(attacker, defender, skill_meta, weather=weather)
        if dr is None:
            return None

        special_rule = self._special_rule_store.get(dr.skill_id)
        ruled = self._apply_special_rule(dr, special_rule)
        calibration = self._calibration_store.get(ruled.skill_id)
        adjusted = self._apply_calibration(ruled, calibration)
        flags = self._accuracy_flags(adjusted, calibration)
        confidence = self._confidence(adjusted.confidence, flags)
        validation_hint = self._validation_hint(flags)
        explain = self._explain(adjusted, calibration, special_rule)
        target_hp_before = adjusted.damage_breakdown.get("defender_current_hp") or 0
        predicted_hp_after = max(0, int(target_hp_before) - adjusted.total_damage)
        runtime_sources = adjusted.damage_breakdown.get("runtime_sources") or {}
        audit_key = self._audit_key(adjusted, defender)

        return {
            "result": adjusted,
            "prediction": {
                "audit_key": audit_key,
                "per_hit": adjusted.expected_damage,
                "total": adjusted.total_damage,
                "hit_count": adjusted.hit_count,
                "target_hp_before": target_hp_before,
                "predicted_hp_after": predicted_hp_after,
                "runtime_sources": runtime_sources,
                "confidence": confidence,
                "accuracy_flags": flags,
            },
            "explain": explain,
            "validation_hint": validation_hint,
        }

    @staticmethod
    def _apply_special_rule(dr: DamageResult, rule: SpecialDamageRule) -> DamageResult:
        special = dr.damage_breakdown.get("special_damage_rule")
        if special is None:
            return dr
        data = dr.to_dict()
        if rule.is_present and rule.per_hit is not None and rule.hit_count is not None:
            per_hit = int(rule.per_hit)
            hit_count = max(1, int(rule.hit_count))
            total = per_hit * hit_count
            defender_max_hp = dr.damage_breakdown.get("defender_max_hp") or 1
            defender_cur_hp = dr.damage_breakdown.get("defender_current_hp") or 0
            data["expected_damage"] = per_hit
            data["hit_count"] = hit_count
            data["pct_hp"] = round(total / max(1, defender_max_hp), 3)
            data["can_ko"] = total >= defender_cur_hp
        rule_payload = rule.to_dict() if rule.is_present else {}
        data["confidence"] = "low" if not rule.is_present else dr.confidence
        data["damage_breakdown"] = {
            **dr.damage_breakdown,
            "special_damage_rule": {
                **special,
                **rule_payload,
                "source": "config" if rule.is_present else special.get("source", "config_missing"),
            },
        }
        return DamageResult(**{
            key: value
            for key, value in data.items()
            if key in DamageResult.__dataclass_fields__
        })

    @staticmethod
    def _apply_calibration(dr: DamageResult, calibration: DamageCalibration) -> DamageResult:
        if not calibration.is_present or calibration.multiplier == 1.0:
            return dr
        adjusted = int(max(1, round(dr.expected_damage * calibration.multiplier)))
        total = adjusted * dr.hit_count
        defender_max_hp = dr.damage_breakdown.get("defender_max_hp") or 1
        defender_cur_hp = dr.damage_breakdown.get("defender_current_hp") or 0
        data = dr.to_dict()
        data["expected_damage"] = adjusted
        data["pct_hp"] = round(total / max(1, defender_max_hp), 3)
        data["can_ko"] = total >= defender_cur_hp
        data["damage_breakdown"] = {
            **dr.damage_breakdown,
            "calibration_mult": calibration.multiplier,
            "raw_expected_damage": dr.expected_damage,
        }
        return DamageResult(**{
            key: value
            for key, value in data.items()
            if key in DamageResult.__dataclass_fields__
        })

    @staticmethod
    def _accuracy_flags(dr: DamageResult, calibration: DamageCalibration) -> List[str]:
        flags: List[str] = []
        stat_sources = dr.damage_breakdown.get("stat_sources", {})
        runtime_sources = dr.damage_breakdown.get("runtime_sources") or {}
        if "wiki" in {stat_sources.get("attack"), stat_sources.get("defense")}:
            flags.append("estimated_stats")
        if calibration.is_present:
            flags.append("calibrated")
        else:
            flags.append("uncalibrated_skill")
        if dr.hit_count > 1:
            flags.append("multi_hit")
        if dr.damage_breakdown.get("special_damage_rule"):
            rule = dr.damage_breakdown["special_damage_rule"]
            flags.append("special_fixed_damage")
            if not rule.get("applied"):
                flags.append("special_damage_unmodeled")
        if any("能量不足" in w for w in dr.warnings):
            flags.append("energy_insufficient")
        if dr.confidence == "low":
            flags.append("low_stat_confidence")
        if runtime_sources.get("has_damage_params") and not runtime_sources.get("matched_target_key"):
            flags.append("runtime_target_unmatched")
        if any(
            runtime_sources.get(key)
            for key in ("has_set_cost_info", "has_cr_damage_params", "has_extra_damage_type", "has_skill_buff")
        ):
            flags.append("runtime_effect_unmodeled")
        return flags

    @staticmethod
    def _confidence(base: str, flags: List[str]) -> str:
        if (
            "low_stat_confidence" in flags
            or "estimated_stats" in flags
            or "runtime_target_unmatched" in flags
            or "special_damage_unmodeled" in flags
        ):
            return "low"
        if "uncalibrated_skill" in flags or "multi_hit" in flags or "runtime_effect_unmodeled" in flags:
            return "medium" if base == "high" else base
        return base

    @staticmethod
    def _validation_hint(flags: List[str]) -> Optional[str]:
        hints = {
            "estimated_stats": "攻防属性来自估算，伤害可能偏差较大",
            "uncalibrated_skill": "技能尚未经过回放校准",
            "multi_hit": "多段/动态连击会放大预测误差",
            "energy_insufficient": "当前能量不足，预测仅供参考",
            "low_stat_confidence": "属性来源置信度较低",
            "runtime_target_unmatched": "服务端目标参数未能匹配当前目标",
            "runtime_effect_unmodeled": "存在尚未建模的运行时技能效果",
            "special_fixed_damage": "特殊固定/多段伤害，按专用规则评估",
            "special_damage_unmodeled": "特殊伤害规则尚未提交配置，预测仅供参考",
        }
        selected = [hints[f] for f in flags if f in hints]
        return "；".join(selected) if selected else None

    @staticmethod
    def _explain(
        dr: DamageResult,
        calibration: DamageCalibration,
        special_rule: SpecialDamageRule,
    ) -> Dict[str, Any]:
        bd = dr.damage_breakdown
        return {
            "formula": "int((ATK / DEF) * power * 0.9 * effectiveness * stab * weather * power_mult)",
            "stat_sources": bd.get("stat_sources", {}),
            "multipliers": {
                "effectiveness": dr.effectiveness,
                "stab": 1.5 if dr.is_stab else 1.0,
                "weather": dr.weather_mult,
                "power": dr.power_mult,
                "hit_count": dr.hit_count,
            },
            "hooks": {
                "ability_level": bd.get("ability_level"),
                "damage_reduction": bd.get("damage_reduction"),
                "combo": dr.hit_count > 1,
            },
            "calibration": calibration.to_dict(),
            "special_damage_rule": (
                dr.damage_breakdown.get("special_damage_rule")
                or special_rule.to_dict()
            ),
            "runtime_sources": bd.get("runtime_sources") or {},
            "server_power_rule": bd.get("server_power_rule") or {},
        }

    @staticmethod
    def _audit_key(dr: DamageResult, defender: Dict[str, Any]) -> str:
        target = (
            defender.get("battle_uid")
            or defender.get("pet_id")
            or defender.get("slot")
            or defender.get("name")
            or "?"
        )
        return f"{dr.skill_id}:{target}"
