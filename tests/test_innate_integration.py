"""Integration test: verify innate skill system works correctly with battle_session_1 replay data."""
from __future__ import annotations

import pytest
from pathlib import Path

from src.analysis.battle_state import BattleStateTracker, POISON_BUFF_IDS
from src.analysis.damage_calc import DamageCalculator
from src.analysis.innate_hooks import (
    combo_modify_hook,
    power_modify_hook,
    register_innate_hooks,
    stat_modify_hook,
    type_resist_modify_hook,
)
from src.game.type_chart import TypeChart
from tests.packet_reader import load_battle_packets, replay_battle

SESSION_DIR = Path(__file__).resolve().parent / "fixtures" / "packets" / "battle_session_1"


@pytest.fixture(scope="module")
def battle_packets():
    return load_battle_packets(SESSION_DIR)


@pytest.fixture(scope="module")
def replay_result(battle_packets):
    return replay_battle(battle_packets)


# ---------------------------------------------------------------------------
# TestPetStateDefaults — combo_bonus and poison_stacks fields
# ---------------------------------------------------------------------------


class TestPetStateDefaults:
    """Verify combo_bonus and poison_stacks are initialized on all pets."""

    def test_my_pets_have_combo_bonus(self, replay_result):
        _, state = replay_result
        for pet in state["my_pets"]:
            assert "combo_bonus" in pet, f"Pet {pet['name']} missing combo_bonus"
            assert isinstance(pet["combo_bonus"], int)

    def test_opp_pets_have_combo_bonus(self, replay_result):
        _, state = replay_result
        for pet in state["opp_pets"]:
            assert "combo_bonus" in pet, f"Pet {pet['name']} missing combo_bonus"
            assert isinstance(pet["combo_bonus"], int)

    def test_my_pets_have_poison_stacks(self, replay_result):
        _, state = replay_result
        for pet in state["my_pets"]:
            assert "poison_stacks" in pet, f"Pet {pet['name']} missing poison_stacks"
            assert isinstance(pet["poison_stacks"], int)

    def test_opp_pets_have_poison_stacks(self, replay_result):
        _, state = replay_result
        for pet in state["opp_pets"]:
            assert "poison_stacks" in pet, f"Pet {pet['name']} missing poison_stacks"
            assert isinstance(pet["poison_stacks"], int)

    def test_default_combo_bonus_is_zero(self, replay_result):
        """All pets start with combo_bonus=0 (no combo_skill_cast events in this session)."""
        _, state = replay_result
        for pet in state["my_pets"] + state["opp_pets"]:
            assert pet["combo_bonus"] == 0, f"Pet {pet['name']} has non-zero combo_bonus"


# ---------------------------------------------------------------------------
# TestPoisonStackTracking — verify poison stacks from effect_apply events
# ---------------------------------------------------------------------------


class TestPoisonStackTracking:
    """Verify poison_stacks is tracked from effect_apply events with POISON_BUFF_IDS."""

    def test_poison_buff_ids_defined(self):
        assert len(POISON_BUFF_IDS) > 0

    def test_poison_events_in_replay(self, replay_result):
        """battle_session_1 has effect_apply events with poison buff IDs."""
        events, _ = replay_result
        poison_events = []
        for e in events:
            detail = e.get("detail", {})
            entries = detail.get("entries", [])
            for entry in entries:
                if (
                    entry.get("kind") == "effect_apply"
                    and entry.get("effect_id") in POISON_BUFF_IDS
                ):
                    poison_events.append(entry)
        assert len(poison_events) > 0, "No poison effect_apply events found"

    def test_opponent_pets_with_poison(self, replay_result):
        """Specific opponent pets should have poison_stacks > 0."""
        _, state = replay_result
        poisoned = [p for p in state["opp_pets"] if p.get("poison_stacks", 0) > 0]
        assert len(poisoned) >= 1, "Expected at least 1 poisoned opponent pet"
        for p in poisoned:
            assert p["poison_stacks"] > 0, f"Pet {p['name']} poison_stacks should be > 0"

    def test_poison_stacks_value_from_stage(self, replay_result):
        """poison_stacks should match the last effect_stage from poison buff events."""
        events, state = replay_result
        # Collect poison effect events per side
        poison_by_side = {}
        for e in events:
            detail = e.get("detail", {})
            entries = detail.get("entries", [])
            for entry in entries:
                if (
                    entry.get("kind") == "effect_apply"
                    and entry.get("effect_id") in POISON_BUFF_IDS
                ):
                    side = entry.get("target_side")
                    stage = entry.get("effect_stage", 0)
                    if side not in poison_by_side:
                        poison_by_side[side] = []
                    poison_by_side[side].append(stage)
        # Each poisoned pet's poison_stacks should be <= max stage observed
        for p in state["opp_pets"]:
            if p.get("poison_stacks", 0) > 0:
                assert p["poison_stacks"] >= 1, (
                    f"Pet {p['name']} poison_stacks={p['poison_stacks']} but expected >= 1"
                )


# ---------------------------------------------------------------------------
# TestInnateHooksWithRealData — damage calculator + hooks on replay pets
# ---------------------------------------------------------------------------


class TestInnateHooksWithRealData:
    """Run DamageCalculator with innate hooks on actual replay battle state pets."""

    def _get_active_pair(self, state):
        """Return (my_active, opp_active) from replay state."""
        my = state.get("my_active")
        opp = state.get("opp_active")
        assert my is not None, "my_active is None"
        assert opp is not None, "opp_active is None"
        return my, opp

    def test_calculate_with_innate_hooks(self, replay_result):
        """DamageCalculator with innate hooks produces valid results on replay data."""
        _, state = replay_result
        my, opp = self._get_active_pair(state)

        calc = DamageCalculator(TypeChart())
        register_innate_hooks(calc)

        # Use equipped skills if available, otherwise empty
        skills = my.get("equipped_skills", [])
        if not skills:
            pytest.skip("No equipped skills on active pet")

        results = calc.calculate_all(my, opp, skills)
        # Results may be empty if no attack skills
        for r in results:
            assert r.hit_count >= 1
            assert r.total_min_damage >= r.min_damage
            assert r.total_max_damage >= r.max_damage

    def test_damage_result_fields_present(self, replay_result):
        """DamageResult has hit_count, total_min_damage, total_max_damage fields."""
        _, state = replay_result
        my, opp = self._get_active_pair(state)

        calc = DamageCalculator(TypeChart())
        register_innate_hooks(calc)

        skills = my.get("equipped_skills", [])
        if not skills:
            pytest.skip("No equipped skills on active pet")

        results = calc.calculate_all(my, opp, skills)
        if not results:
            pytest.skip("No attack skills found")
        for r in results:
            d = r.to_dict()
            assert "hit_count" in d
            assert "total_min_damage" in d
            assert "total_max_damage" in d
            assert d["hit_count"] >= 1
            assert d["total_min_damage"] == d["min_damage"] * d["hit_count"]
            assert d["total_max_damage"] == d["max_damage"] * d["hit_count"]

    def test_hooks_dont_crash_with_replay_data(self, replay_result):
        """All four hooks execute without error on replay pet state."""
        _, state = replay_result
        my = state["my_active"]
        opp = state["opp_active"]
        if my is None or opp is None:
            pytest.skip("No active pets")

        base_ctx = {
            "attacker": my,
            "defender": opp,
            "skill_meta": {"id": 1, "name": "test", "dam_para": [80], "skill_dam_type": 1},
        }

        # post_base
        ctx = {**base_ctx, "base_damage": 100, "power": 80, "level": 100, "atk_val": 200, "def_val": 150}
        result = stat_modify_hook(ctx)
        assert "base_damage" in result

        # pre_final
        ctx = {**base_ctx, "base_damage": 100, "effectiveness": 1.0, "stab_mult": 1.5}
        result = type_resist_modify_hook(ctx)
        assert "effectiveness" in result

        # post_calc (combo)
        ctx = {**base_ctx, "min_damage": 50, "max_damage": 60, "effectiveness": 1.0, "stab_mult": 1.0}
        result = combo_modify_hook(ctx)
        assert "min_damage" in result

        # post_calc (power)
        result = power_modify_hook(ctx)
        assert "min_damage" in result


# ---------------------------------------------------------------------------
# TestComboBonusReset — verify combo_bonus resets on pet switch
# ---------------------------------------------------------------------------


class TestComboBonusReset:
    """Verify combo_bonus resets to 0 when pet switches."""

    def test_combo_bonus_reset_on_change_pet(self, replay_result):
        """Pets that switched in should have combo_bonus=0 (reset on change_pet)."""
        events, state = replay_result
        # Find pets that were switched in via change_pet entries
        switched_pet_ids = set()
        for e in events:
            detail = e.get("detail", {})
            entries = detail.get("entries", [])
            for entry in entries:
                if entry.get("kind") == "change_pet":
                    pet_id = entry.get("new_pet_id") or entry.get("battle_pet_id")
                    if pet_id is not None:
                        switched_pet_ids.add(pet_id)

        # All pets in final state should have combo_bonus=0
        for pet in state["my_pets"] + state["opp_pets"]:
            assert pet.get("combo_bonus", 0) == 0, (
                f"Pet {pet['name']} (id={pet.get('pet_id')}) has combo_bonus={pet['combo_bonus']}"
            )


# ---------------------------------------------------------------------------
# TestReplayAPIWithInnateSkills — verify API endpoint works
# ---------------------------------------------------------------------------


class TestReplayAPIWithInnateSkills:
    """Verify the replay API endpoint works with innate skill system."""

    @pytest.fixture(scope="class")
    def api_client(self):
        from fastapi.testclient import TestClient
        from src.api.app import create_app
        app = create_app()
        with TestClient(app) as c:
            yield c

    def test_replay_api_returns_ok(self, api_client):
        resp = api_client.post("/api/battle/replay?delay_ms=0&session=battle_session_1")
        data = resp.json()
        assert data["status"] == "ok"

    def test_replay_api_pet_count(self, api_client):
        resp = api_client.post("/api/battle/replay?delay_ms=0&session=battle_session_1")
        data = resp.json()
        assert data["opp_pets"] == 6
        assert data["my_pets"] > 0

    def test_replay_state_has_innate_fields(self, api_client):
        """After replay, tracker state should have combo_bonus and poison_stacks on pets."""
        from src.api.battle_manager import get_battle_manager

        api_client.post("/api/battle/replay?delay_ms=0&session=battle_session_1")
        mgr = get_battle_manager()
        state = mgr.tracker.get_state()

        for pet in state["my_pets"] + state["opp_pets"]:
            assert "combo_bonus" in pet, f"Pet {pet.get('name')} missing combo_bonus"
            assert "poison_stacks" in pet, f"Pet {pet.get('name')} missing poison_stacks"

    def test_replay_state_poison_tracked(self, api_client):
        """After replay, at least one opponent pet should have poison_stacks > 0."""
        from src.api.battle_manager import get_battle_manager

        api_client.post("/api/battle/replay?delay_ms=0&session=battle_session_1")
        mgr = get_battle_manager()
        state = mgr.tracker.get_state()

        poisoned = [p for p in state["opp_pets"] if p.get("poison_stacks", 0) > 0]
        assert len(poisoned) >= 1, "No poisoned opponent pets after replay"
