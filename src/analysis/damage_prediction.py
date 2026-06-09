"""统一技能伤害预测服务。

该模块把 DamageCalculator 的公式结果包装成可解释、可校准、可对账的输出。
旧字段仍由调用方写回 SkillAnalysis；新增 prediction/explain/validation_hint 用于前端和回放校验。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analysis.damage.result import DamageResult
from src.analysis.damage_calc import DamageCalculator
from src.analysis.damage.prediction_config import (
    DamageCalibration,
    DamageCalibrationStore,
    ServerPowerRuleStore,
    SpecialDamageRule,
    SpecialDamageRuleStore,
)
from src.analysis.damage import prediction_output
from src.analysis.innate_hooks import register_innate_hooks
from src.game.type_chart import TypeChart


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
        return prediction_output.build_prediction_payload(
            adjusted,
            defender,
            calibration,
            special_rule,
        )

    @staticmethod
    def _apply_special_rule(dr: DamageResult, rule: SpecialDamageRule) -> DamageResult:
        return prediction_output.apply_special_rule(dr, rule)

    @staticmethod
    def _apply_calibration(dr: DamageResult, calibration: DamageCalibration) -> DamageResult:
        return prediction_output.apply_calibration(dr, calibration)

    @staticmethod
    def _accuracy_flags(dr: DamageResult, calibration: DamageCalibration) -> List[str]:
        return prediction_output.accuracy_flags(dr, calibration)

    @staticmethod
    def _confidence(base: str, flags: List[str]) -> str:
        return prediction_output.prediction_confidence(base, flags)

    @staticmethod
    def _validation_hint(flags: List[str]) -> Optional[str]:
        return prediction_output.validation_hint(flags)

    @staticmethod
    def _secondary_effects(dr: DamageResult, defender: Dict[str, Any]) -> List[Dict[str, Any]]:
        return prediction_output.secondary_effects(dr, defender)

    @staticmethod
    def _explain(
        dr: DamageResult,
        calibration: DamageCalibration,
        special_rule: SpecialDamageRule,
    ) -> Dict[str, Any]:
        return prediction_output.explain_prediction(dr, calibration, special_rule)

    @staticmethod
    def _audit_key(dr: DamageResult, defender: Dict[str, Any]) -> str:
        return prediction_output.audit_key(dr, defender)
