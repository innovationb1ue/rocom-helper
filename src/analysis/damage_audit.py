"""回放伤害预测对账兼容入口。

只统计带技能名的直接技能伤害；中毒、天气、回合末等无技能名伤害不进入准确率指标。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.analysis.damage.audit_calibration import (
    build_damage_calibration as _build_damage_calibration,
    build_special_damage_rules as _build_special_damage_rules,
)
from src.analysis.damage.audit_mechanism import (
    build_mechanism_report,
    build_multi_session_mechanism_report,
)
from src.analysis.damage.audit_samples import (
    DamageAuditSample,
    DamageMechanismSample,
    iter_damage_audit_samples,
    iter_damage_mechanism_samples,
    ledger_actual_damage as _ledger_actual_damage,
    ledger_records_for_damage as _ledger_records_for_damage,
)
from src.analysis.damage.audit_summary import (
    summarize_damage_samples,
    summarize_multi_session_damage_audit,
)
from src.analysis.replay_runner import ReplayResult


def build_damage_audit(result: ReplayResult) -> Dict[str, Any]:
    samples = list(iter_damage_audit_samples(result))
    return summarize_damage_samples([sample.to_dict() for sample in samples])


def build_damage_mechanism_report(
    result: ReplayResult,
    *,
    session: Optional[str] = None,
) -> Dict[str, Any]:
    """生成技能运行时伤害参数机制审计报告。"""
    samples = [sample.to_dict() for sample in iter_damage_mechanism_samples(result, session=session)]
    return build_mechanism_report(samples)


def build_multi_session_damage_mechanism_report(
    reports: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """聚合多场机制审计报告。"""
    return build_multi_session_mechanism_report(reports)


def build_multi_session_damage_audit(reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate several damage-audit reports without losing per-session detail."""
    return summarize_multi_session_damage_audit(reports)


def build_damage_calibration(
    report: Dict[str, Any],
    *,
    min_samples: int = 3,
) -> Dict[str, Any]:
    """从审计报告生成只读校准配置草案。"""
    return _build_damage_calibration(report, min_samples=min_samples)


def build_special_damage_rules(report: Dict[str, Any]) -> Dict[str, Any]:
    """从协议账本生成特殊固定伤害规则草案。

    折射（7060130）已确认是光系魔伤，派生效果在本体伤害后结算，
    不能从其低伤害样本反推固定伤害规则。
    """
    return _build_special_damage_rules(report)
