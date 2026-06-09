from __future__ import annotations

from src.analysis.advisor.skill_analysis import eval_skill_dict, skill_from_equipped


def test_skill_from_equipped_prefers_runtime_energy_and_metadata_fallbacks():
    eq = {
        "skill_id": 7000170,
        "equipped_slot": 2,
        "runtime_cost_energy": 3,
    }
    meta = {
        "name": "元数据名",
        "damage_type": 2,
        "energy_cost": [8],
        "desc": "技能描述",
        "skill_dam_type": 7,
    }

    result = skill_from_equipped(eq, meta)

    assert result.skill_id == 7000170
    assert result.equipped_slot == 2
    assert result.energy_cost == 3
    assert result.skill_damage_type == 2
    assert result.skill_desc == "技能描述"
    assert result.skill_element != 0


def test_eval_skill_dict_normalizes_skill_eval_inputs_from_metadata():
    eq = {"skill_element": 1, "cost_energy": 0}
    meta = {
        "dam_para": [90],
        "energy_cost": [4],
        "hit_para": 9500,
        "max_pp": 12,
        "desc": "造成伤害",
        "skill_dam_type": 1,
    }

    result = eval_skill_dict(eq, meta)

    assert result["power"] == 90
    assert result["energy_cost"] == 4
    assert result["accuracy"] == 95
    assert result["pp"] == 12
    assert result["effect_desc"] == "造成伤害"
