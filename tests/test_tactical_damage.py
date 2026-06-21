"""战术伤害工具测试。"""
from __future__ import annotations

from src.analysis.tactical import damage as tactical_damage


class FakePredictionService:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def predict(self, attacker, defender, skill_meta, weather=None):
        self.calls.append((attacker, defender, skill_meta, weather))
        return self.payload


class FakeChart:
    def __init__(self, multipliers):
        self.multipliers = multipliers

    def get_multiplier(self, attack_type, defend_types):
        return self.multipliers.get((attack_type, tuple(defend_types)), 1.0)


def _toolkit(payload, chart=None):
    return tactical_damage.TacticalDamageToolkit(
        chart=chart or FakeChart({}),
        prediction_service=FakePredictionService(payload),
    )


def test_calc_damage_prefers_tactical_total():
    toolkit = _toolkit({"prediction": {"total": 80, "tactical_total": 95}})

    damage = toolkit.calc_damage(
        {"name": "我方"},
        {"name": "敌方"},
        {"damage_type": 2},
        {"name": "天气"},
    )

    assert damage == 95


def test_calc_damage_falls_back_to_total():
    toolkit = _toolkit({"prediction": {"total": 80}})

    assert toolkit.calc_damage({}, {}, {"damage_type": 3}, None) == 80


def test_calc_damage_skips_non_damage_skill_without_prediction_call():
    service = FakePredictionService({"prediction": {"tactical_total": 95}})
    toolkit = tactical_damage.TacticalDamageToolkit(
        chart=FakeChart({}),
        prediction_service=service,
    )

    assert toolkit.calc_damage({}, {}, {"damage_type": 1}, None) == 0
    assert toolkit.calc_damage({}, {}, None, None) == 0
    assert service.calls == []


def test_calc_damage_returns_zero_without_prediction():
    toolkit = _toolkit(None)

    assert toolkit.calc_damage({}, {}, {"damage_type": 2}, None) == 0


def test_type_matchup_score_uses_best_attacking_type():
    chart = FakeChart({
        (1, (3,)): 0.5,
        (2, (3,)): 2.0,
    })
    toolkit = tactical_damage.TacticalDamageToolkit(
        chart=chart,
        prediction_service=FakePredictionService(None),
    )

    assert toolkit.type_matchup_score({"types": [1, 2]}, {"types": [3]}) == 2.0


def test_type_matchup_score_defaults_when_type_data_missing():
    toolkit = tactical_damage.TacticalDamageToolkit(
        chart=FakeChart({}),
        prediction_service=FakePredictionService(None),
    )

    assert toolkit.type_matchup_score({"types": []}, {"types": [1]}) == 1.0
    assert toolkit.type_matchup_score({"types": [1]}, {"types": []}) == 1.0
