"""数据加载器测试 — 使用真实 JSON 数据文件。"""
from __future__ import annotations

import sys
import io
import pytest
from src.data.loader import (
    get_bundle,
    get_attr_meta,
    get_attr_name,
    get_skill_meta,
    get_skill_name,
    get_pet_meta,
    get_pet_name,
    get_buff_meta,
    get_pet_skill_meta,
    get_buff_stat_modifiers,
    invalidate_cache,
    DATA_DIR,
)


@pytest.fixture(autouse=True)
def _fresh_cache(request):
    """Only invalidate cache for tests that explicitly test caching behavior."""
    if "TestCacheInvalidation" in request.node.nodeid:
        invalidate_cache()
        yield
        invalidate_cache()
    else:
        yield


def _utf8_print(text: str) -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(text)


class TestBundleLoading:
    """整体数据加载测试。"""

    def test_bundle_loads(self):
        bundle = get_bundle()
        assert isinstance(bundle, dict)
        assert len(bundle) > 0

    def test_attr_meta_loaded(self):
        bundle = get_bundle()
        attr = bundle.get("attr_meta", {})
        assert len(attr) >= 18, f"Expected >= 18 attributes, got {len(attr)}"

    def test_skill_meta_loaded(self):
        bundle = get_bundle()
        skills = bundle.get("skill_meta", {})
        assert len(skills) > 100, f"Expected > 100 skills, got {len(skills)}"

    def test_pet_meta_loaded(self):
        bundle = get_bundle()
        pets = bundle.get("pet_meta", {})
        assert len(pets) > 100, f"Expected > 100 pets, got {len(pets)}"

    def test_buff_meta_loaded(self):
        bundle = get_bundle()
        buffs = bundle.get("buff_meta", {})
        assert len(buffs) > 0


class TestAttrLookup:
    """属性查询测试。"""

    def test_attr_name_known_id(self):
        name = get_attr_name(1)
        assert name is not None
        assert isinstance(name, str)
        assert len(name) > 0

    def test_attr_meta_has_expected_fields(self):
        meta = get_attr_meta(1)
        assert meta is not None
        assert "name" in meta
        assert "id" in meta

    def test_attr_not_found(self):
        assert get_attr_name(999999) is None
        assert get_attr_meta(999999) is None


class TestSkillLookup:
    """技能查询测试。"""

    def test_skill_name_known_id(self):
        # 7700001 = 愿力冲击 (from verified data)
        name = get_skill_name(7700001)
        assert name is not None

    def test_skill_meta_has_fields(self):
        meta = get_skill_meta(7700001)
        assert meta is not None
        assert "name" in meta

    def test_skill_not_found(self):
        assert get_skill_name(999999999) is None

    def test_skill_id_normalization(self):
        # Skill IDs >= 100_000 ending in 00 should be normalized (divided by 100)
        meta_normalized = get_skill_meta(7700000)
        meta_direct = get_skill_meta(77000)
        # At least one should work - depends on data
        # The normalization: 7700000 -> 77000
        # Check that the normalization function works
        from src.data.loader import _normalize_skill_id
        assert _normalize_skill_id(7700000) == 77000
        assert _normalize_skill_id(100) == 100  # not normalized


class TestPetLookup:
    """精灵查询测试。"""

    def test_pet_name_known_id(self):
        # 14000001 = 喵喵 (from verified data)
        name = get_pet_name(14000001)
        assert name is not None

    def test_pet_meta_has_fields(self):
        meta = get_pet_meta(14000001)
        assert meta is not None
        assert "name" in meta
        assert "id" in meta

    def test_pet_base_id(self):
        meta = get_pet_meta(14000001)
        assert meta is not None
        assert "base_id" in meta

    def test_pet_not_found(self):
        assert get_pet_name(999999999) is None

    def test_pet_fallback_to_monster(self):
        # get_pet_meta tries pet_meta first, then monster_meta
        # Just verify the function doesn't crash
        result = get_pet_meta(1)
        # May or may not exist, just verify no exception
        assert result is None or isinstance(result, dict)


class TestBuffLookup:
    """Buff 查询测试。"""

    def test_buff_meta_returns_dict_or_none(self):
        result = get_buff_meta(1)
        assert result is None or isinstance(result, dict)

    def test_buff_meta_not_found(self):
        assert get_buff_meta(0) is None


class TestPetSkillLookup:
    """精灵技能池查询测试。"""

    def test_pet_skill_meta_returns_dict_or_none(self):
        result = get_pet_skill_meta(3001)
        assert result is None or isinstance(result, dict)


class TestCacheInvalidation:
    """缓存失效测试。"""

    def test_invalidate_and_reload(self):
        bundle1 = get_bundle()
        invalidate_cache()
        bundle2 = get_bundle()
        assert bundle1 is not bundle2  # different objects after invalidation
        # Same content
        assert len(bundle1.get("attr_meta", {})) == len(bundle2.get("attr_meta", {}))


class TestDataDir:
    """数据目录存在性测试。"""

    def test_data_dir_exists(self):
        assert DATA_DIR.exists()

    def test_required_files_exist(self):
        required = ["attr_map.json", "skill_map.json", "pet_map.json", "buff_map.json"]
        for fname in required:
            assert (DATA_DIR / fname).exists(), f"Missing {fname}"


class TestBuffStatModifiers:
    """Buff 属性修正查询测试。"""

    def test_empty_buff_list(self):
        assert get_buff_stat_modifiers([]) == {}

    def test_unknown_buff_id(self):
        result = get_buff_stat_modifiers([{"id": 999999999}])
        assert result == {}

    def test_known_buff_modifier_scale(self):
        """助燃 (buff_id=20011521) has buff_base_ids=[2001001, 2001002].
        2001001: attr=29 (atk_up), value=1000 → 1000/10000 = 0.1
        2001002: attr=30 (spa_up), value=1000 → 1000/10000 = 0.1
        At stage=1: atk_up=0.1, spa_up=0.1"""
        result = get_buff_stat_modifiers([{"id": 20011521, "stage": 1}])
        assert abs(result.get("atk_up", 0.0) - 0.1) < 0.001
        assert abs(result.get("spa_up", 0.0) - 0.1) < 0.001

    def test_stage_multiplies_modifier(self):
        """Stage=2 should double the modifier."""
        r1 = get_buff_stat_modifiers([{"id": 20011521, "stage": 1}])
        r2 = get_buff_stat_modifiers([{"id": 20011521, "stage": 2}])
        assert abs(r2["atk_up"] - r1["atk_up"] * 2) < 0.001
        assert abs(r2["spa_up"] - r1["spa_up"] * 2) < 0.001

    def test_missing_stage_defaults_to_1(self):
        """Buff without stage field should default to stage=1."""
        r_no_stage = get_buff_stat_modifiers([{"id": 20011521}])
        r_stage_1 = get_buff_stat_modifiers([{"id": 20011521, "stage": 1}])
        assert abs(r_no_stage["atk_up"] - r_stage_1["atk_up"]) < 0.001

    def test_zero_stage_clamped_to_1(self):
        """Stage=0 should be clamped to 1."""
        r0 = get_buff_stat_modifiers([{"id": 20011521, "stage": 0}])
        r1 = get_buff_stat_modifiers([{"id": 20011521, "stage": 1}])
        assert abs(r0["atk_up"] - r1["atk_up"]) < 0.001

    def test_multiple_buffs_accumulate(self):
        """Multiple buffs should sum their modifiers."""
        r = get_buff_stat_modifiers([
            {"id": 20011521, "stage": 1},  # atk_up=0.1, spa_up=0.1
            {"id": 20011521, "stage": 2},  # atk_up=0.2, spa_up=0.2
        ])
        assert abs(r["atk_up"] - 0.3) < 0.001
        assert abs(r["spa_up"] - 0.3) < 0.001

    def test_defensive_buff_modifier(self):
        """物防等级提升10 (buffbase 2001005): attr=31 (def_up), value=1000 → 0.1."""
        # Find a buff that uses buffbase 2001005
        bundle = get_bundle()
        buff_meta = bundle.get("buff_meta", {})
        bb_meta = bundle.get("buffbase_meta", {})
        target_buff_id = None
        for bid, bentry in buff_meta.items():
            base_ids = bentry.get("buff_base_ids", [])
            if 2001005 in base_ids and len(base_ids) == 1:
                target_buff_id = bid
                break
        if target_buff_id is None:
            pytest.skip("No single-base buff with buffbase 2001005 found")
        result = get_buff_stat_modifiers([{"id": target_buff_id, "stage": 1}])
        assert abs(result.get("def_up", 0.0) - 0.1) < 0.001
