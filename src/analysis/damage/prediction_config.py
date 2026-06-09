"""伤害预测服务使用的只读配置 store。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import settings

CALIBRATION_PATH = settings.config_dir / "damage_calibration.json"
SPECIAL_RULES_PATH = settings.config_dir / "special_damage_rules.json"
SERVER_POWER_RULES_PATH = settings.config_dir / "server_power_rules.json"


def _load_json_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"version": 1, "skills": {}}
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "skills": {}}
    return data if isinstance(data, dict) else {"version": 1, "skills": {}}


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

    def __init__(self, path: Path = SPECIAL_RULES_PATH) -> None:
        self.path = path
        self._data: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        if self._data is None:
            self._data = _load_json_config(self.path)
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
            source_sessions=tuple(str(session) for session in sessions),
            notes=str(raw.get("notes", "")),
            key=str(skill_id),
        )


class ServerPowerRuleStore:
    """读取按技能启用的服务器威力规则。v1 只读。"""

    def __init__(self, path: Path = SERVER_POWER_RULES_PATH) -> None:
        self.path = path
        self._data: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        if self._data is None:
            self._data = _load_json_config(self.path)
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

    def __init__(self, path: Path = CALIBRATION_PATH) -> None:
        self.path = path
        self._data: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        if self._data is None:
            self._data = _load_json_config(self.path)
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
            source_sessions=tuple(str(session) for session in sessions),
            notes=str(raw.get("notes", "")),
            key=str(skill_id),
        )
