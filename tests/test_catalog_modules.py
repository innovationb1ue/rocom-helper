"""基础 catalog 子模块测试。"""
from __future__ import annotations

from pathlib import Path

from src.data import catalog
from src.data.catalog_bundle import (
    _int_keyed_meta,
    get_bundle,
    get_maps,
    invalidate_catalog_cache,
)
from src.data.catalog_files import DATA_DIR, _JSON_PATHS, _read_json_dict, _safe_int
from src.data.catalog_lookup import (
    _normalize_skill_id,
    get_attr_meta,
    get_attr_name,
    get_buff_meta,
    get_pet_meta,
    get_pet_name,
    get_skill_meta,
    get_skill_name,
)


def test_catalog_files_read_json_dict_and_safe_int():
    assert DATA_DIR.exists()
    assert _JSON_PATHS["attr_meta"].name == "attr_map.json"
    assert _safe_int(" 42 ") == 42
    assert _safe_int("") is None
    assert _safe_int("x") is None

    attr_raw = _read_json_dict(_JSON_PATHS["attr_meta"])
    assert isinstance(attr_raw, dict)
    assert len(attr_raw) >= 18
    assert _read_json_dict(Path("__missing_catalog_file__.json")) == {}


def test_catalog_bundle_loads_int_keyed_maps_and_invalidates():
    assert _int_keyed_meta({"1": {"name": "一"}, "x": {"name": "坏"}, "2": []}) == {
        1: {"name": "一"}
    }

    invalidate_catalog_cache()
    bundle1 = get_bundle()
    maps1 = get_maps()
    invalidate_catalog_cache()
    bundle2 = get_bundle()
    maps2 = get_maps()

    assert bundle1 is not bundle2
    assert maps1 is not maps2
    assert len(bundle2.get("skill_meta", {})) > 100
    assert {"attr", "pet", "skill"}.issubset(maps2)


def test_catalog_lookup_queries_and_skill_normalization():
    assert _normalize_skill_id(None) is None
    assert _normalize_skill_id(0) is None
    assert _normalize_skill_id(7700000) == 77000
    assert _normalize_skill_id(7700001) == 7700001

    assert get_attr_meta(1) is not None
    assert isinstance(get_attr_name(1), str)
    assert get_skill_meta(7700001) is not None
    assert isinstance(get_skill_name(7700001), str)
    assert get_pet_meta(14000001) is not None
    assert isinstance(get_pet_name(14000001), str)
    assert get_buff_meta(999999999) is None


def test_catalog_facade_preserves_old_import_paths():
    assert catalog.DATA_DIR == DATA_DIR
    assert catalog._JSON_PATHS is _JSON_PATHS
    assert catalog.get_bundle() is get_bundle()
    assert catalog.get_attr_name(1) == get_attr_name(1)
    assert catalog.get_skill_name(7700001) == get_skill_name(7700001)
