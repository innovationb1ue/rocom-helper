"""Pure scoring helpers for TacticalEngine."""
from __future__ import annotations

from typing import Any, Dict

from src.analysis.models import ResolvedOutcome

W_DAMAGE_DEALT = 0.25
W_KO = 0.30
W_DAMAGE_TAKEN = 0.15
W_OPP_KO = 0.20
W_TYPE_MATCHUP = 0.05
W_ENERGY = 0.03
W_COUNT_ADV = 0.02


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def evaluate_outcome(
    outcome: ResolvedOutcome,
    my_active: Dict[str, Any],
    opp_active: Dict[str, Any],
) -> float:
    """将推演结果转为分数。"""
    our_max_hp = max(1, my_active.get("max_hp", 1))
    opp_max_hp = max(1, opp_active.get("max_hp", 1))

    score = (
        W_DAMAGE_DEALT * clamp01(outcome.our_damage_dealt / opp_max_hp)
        + W_KO * (1.0 if outcome.we_ko else 0.0)
        - W_DAMAGE_TAKEN * clamp01(outcome.opp_damage_dealt / our_max_hp)
        - W_OPP_KO * (1.0 if outcome.opp_kos_us else 0.0)
        + W_TYPE_MATCHUP * clamp01(outcome.type_matchup_after / 4.0)
        + W_ENERGY * clamp01(outcome.energy_after / 10.0)
        + W_COUNT_ADV * outcome.pet_count_delta * 0.15
    )

    if outcome.incoming_energy > 0:
        score += 0.02 * clamp01(outcome.incoming_energy / 10.0)
    if outcome.incoming_has_buffs:
        score += 0.03

    return score
