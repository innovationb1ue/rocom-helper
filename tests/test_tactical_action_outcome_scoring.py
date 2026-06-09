"""战术行动 outcome 聚合评分测试。"""
from __future__ import annotations

from src.analysis.models import OpponentAction, ResolvedOutcome
from src.analysis.tactical import action_outcome_scoring


def _pet(name="宠", hp=300, max_hp=300):
    return {
        "name": name,
        "current_hp": hp,
        "max_hp": max_hp,
        "hp_pct": hp / max_hp,
        "energy": 10,
    }


def _damage_action():
    return {
        "action_type": "skill",
        "skill_name": "强攻",
        "is_damage_skill": True,
        "meta": {"damage_type": 2, "dam_para": [100]},
    }


def _outcome(our_damage, opp_damage, we_ko=False):
    return ResolvedOutcome(
        our_damage_dealt=our_damage,
        opp_damage_dealt=opp_damage,
        we_ko=we_ko,
        opp_kos_us=False,
        we_act_first=True,
        our_remaining_hp=200,
        opp_remaining_hp=100,
        type_matchup_after=1.0,
        energy_after=8,
        pet_count_delta=0,
    )


def test_score_expected_outcomes_aggregates_weighted_score_and_extremes():
    my = _pet("我方", hp=300)
    opp = _pet("敌方", hp=100)
    outcomes = [_outcome(40, 20), _outcome(90, 50, we_ko=True)]

    def resolve(_our_action, opp_action, *_args):
        return outcomes[opp_action.skill_id - 1]

    result = action_outcome_scoring.score_expected_outcomes(
        _damage_action(),
        my,
        opp,
        [my],
        [opp],
        [
            OpponentAction(action_type="skill", skill_id=1, probability=0.25),
            OpponentAction(action_type="skill", skill_id=2, probability=0.75),
        ],
        {"weather": None},
        resolve_outcome=resolve,
        calc_damage=lambda *_args: 80,
    )

    assert result.total_score > 0
    assert result.best_damage_dealt == 90
    assert result.worst_damage_taken == 50
    assert result.can_ko is True
    assert result.display_damage_dealt == 80
    assert result.display_can_ko is False
    assert result.shown_damage == 80
    assert result.shown_can_ko is True


def test_top_threat_ko_gets_score_bonus():
    my = _pet("我方", hp=300)
    opp = _pet("威胁", hp=100)

    def resolve(_our_action, _opp_action, *_args):
        return _outcome(120, 0, we_ko=True)

    base = action_outcome_scoring.score_expected_outcomes(
        _damage_action(),
        my,
        opp,
        [my],
        [opp],
        [OpponentAction(action_type="skill", skill_id=1, probability=1.0)],
        {},
        resolve_outcome=resolve,
        calc_damage=lambda *_args: 120,
    )
    boosted = action_outcome_scoring.score_expected_outcomes(
        _damage_action(),
        my,
        opp,
        [my],
        [opp],
        [OpponentAction(action_type="skill", skill_id=1, probability=1.0)],
        {},
        resolve_outcome=resolve,
        calc_damage=lambda *_args: 120,
        top_threat_name="威胁",
    )

    assert boosted.total_score == base.total_score * 1.15


def test_preview_damage_skips_non_damage_actions():
    assert action_outcome_scoring.preview_damage(
        {"action_type": "switch"},
        _pet("我方"),
        _pet("敌方"),
        {},
        calc_damage=lambda *_args: 999,
    ) is None
