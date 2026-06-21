"""回放伤害审计样本提取。"""
from __future__ import annotations

from typing import Iterable, Optional

from src.analysis.damage.audit_ledger import (
    find_prediction,
    ledger_actual_damage,
    ledger_records_for_damage,
)
from src.analysis.damage.audit_direct_samples import (
    iter_damage_audit_samples as iter_direct_damage_audit_samples,
)
from src.analysis.damage.audit_mechanism_samples import (
    iter_damage_mechanism_samples as iter_mechanism_damage_samples,
)
from src.analysis.damage.audit_models import DamageAuditSample, DamageMechanismSample
from src.analysis.damage.audit_runtime import (
    attacker_pet_candidates,
    matched_runtime_value,
    runtime_skill_for_sample,
)
from src.analysis.replay_runner import ReplayResult


def iter_damage_audit_samples(result: ReplayResult) -> Iterable[DamageAuditSample]:
    """兼容入口：普通直接伤害审计样本由 audit_direct_samples 负责。"""
    return iter_direct_damage_audit_samples(result)


def iter_damage_mechanism_samples(
    result: ReplayResult,
    *,
    session: Optional[str] = None,
) -> Iterable[DamageMechanismSample]:
    """兼容入口：机制/runtime 对齐样本由 audit_mechanism_samples 负责。"""
    return iter_mechanism_damage_samples(result, session=session)
