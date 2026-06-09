"""BattleProcessor policy helper tests."""
from __future__ import annotations

from src.analysis.constants import OPCODE_ACTION_RESOLVE, OPCODE_ROUND_START
from src.analysis.processor_policy import (
    battle_is_active,
    should_compute_damage_analysis,
    should_compute_tactical,
    should_snapshot_state_before,
)


def test_battle_is_active_requires_battle_id_and_no_result():
    assert battle_is_active({"battle_id": 1, "result": None}) is True
    assert battle_is_active({"battle_id": None, "result": None}) is False
    assert battle_is_active({"battle_id": 1, "result": "WIN"}) is False


def test_action_resolve_snapshots_state_before_only_when_analysis_enabled():
    assert should_snapshot_state_before(include_analysis=True, opcode=OPCODE_ACTION_RESOLVE) is True
    assert should_snapshot_state_before(include_analysis=False, opcode=OPCODE_ACTION_RESOLVE) is False
    assert should_snapshot_state_before(include_analysis=True, opcode=OPCODE_ROUND_START) is False


def test_damage_analysis_policy_requires_analysis_active_battle_and_damage_opcode():
    damage_opcodes = {OPCODE_ACTION_RESOLVE}

    assert should_compute_damage_analysis(
        include_analysis=True,
        active=True,
        opcode=OPCODE_ACTION_RESOLVE,
        damage_opcodes=damage_opcodes,
    ) is True
    assert should_compute_damage_analysis(
        include_analysis=False,
        active=True,
        opcode=OPCODE_ACTION_RESOLVE,
        damage_opcodes=damage_opcodes,
    ) is False
    assert should_compute_damage_analysis(
        include_analysis=True,
        active=False,
        opcode=OPCODE_ACTION_RESOLVE,
        damage_opcodes=damage_opcodes,
    ) is False
    assert should_compute_damage_analysis(
        include_analysis=True,
        active=True,
        opcode=OPCODE_ROUND_START,
        damage_opcodes=damage_opcodes,
    ) is False


def test_tactical_policy_runs_on_round_start_and_action_resolve_only():
    assert should_compute_tactical(include_analysis=True, active=True, opcode=OPCODE_ACTION_RESOLVE) is True
    assert should_compute_tactical(include_analysis=True, active=True, opcode=OPCODE_ROUND_START) is True
    assert should_compute_tactical(include_analysis=False, active=True, opcode=OPCODE_ROUND_START) is False
    assert should_compute_tactical(include_analysis=True, active=False, opcode=OPCODE_ROUND_START) is False
    assert should_compute_tactical(include_analysis=True, active=True, opcode=0x132C) is False
