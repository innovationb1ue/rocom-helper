"""loader 门面下沉模块测试。"""
from __future__ import annotations

from src.data import loader
from src.data.innate import (
    _load_innate_skills,
    get_innate_skill,
    get_innate_skills_for_pet,
    get_pet_innate_trait,
    reset_innate_caches,
)
from src.data.pet_skills import get_pet_skill_meta
from src.data.wiki_compat import (
    get_wiki_pet,
    get_wiki_pet_stats,
    get_wiki_pet_types,
    get_wiki_skill,
)


def test_pet_skill_meta_lives_in_pet_skills_and_matches_loader_facade():
    direct = get_pet_skill_meta(3001)
    facade = loader.get_pet_skill_meta(3001)

    assert direct is facade
    assert direct is None or isinstance(direct, dict)
    assert get_pet_skill_meta(None) is None


def test_wiki_compat_queries_use_current_bindata_sources():
    pet = get_wiki_pet("喵喵")
    skill = get_wiki_skill("聚能")

    assert pet is not None
    assert pet["name"] == "喵喵"
    assert get_wiki_pet_types("喵喵")
    assert get_wiki_pet_stats("喵喵")["hp"] > 0
    assert skill is not None
    assert skill["name"] == "聚能"

    assert loader.get_wiki_pet("喵喵") == pet
    assert loader.get_wiki_skill("聚能") == skill


def test_innate_queries_and_reset_are_isolated_from_loader_facade():
    reset_innate_caches()
    skills1 = _load_innate_skills()
    skills2 = _load_innate_skills()

    assert skills1 is skills2
    assert get_innate_skill(20030370)["name"] == "免疫绝处逢生"
    assert get_innate_skill(999999999) is None

    trait = get_pet_innate_trait("喵喵")
    assert trait is not None
    assert trait["name"] == "氧循环"
    assert get_pet_innate_trait("__missing__") is None
    assert isinstance(get_innate_skills_for_pet(3001), list)

    assert loader.get_innate_skill(20030370) == get_innate_skill(20030370)
    assert loader.get_pet_innate_trait("喵喵") == trait


def test_loader_invalidate_cache_resets_innate_cache():
    reset_innate_caches()
    skills1 = _load_innate_skills()
    loader.invalidate_cache()
    skills2 = _load_innate_skills()

    assert skills1 is not skills2
