"""配置 API service 测试。"""
from __future__ import annotations

from src.api import config_service
from src.api.config_service import (
    build_learnable_skill_payload,
    list_pets_with_learnable_skills,
    pet_learnable_skills_payload,
    resolve_popular_skill_name,
)


def test_resolve_popular_skill_name_prefers_request_then_pet_meta():
    assert resolve_popular_skill_name(3001, "自定义") == "自定义"
    assert resolve_popular_skill_name(3001, "") == "喵喵"


def test_resolve_popular_skill_name_falls_back_to_skill_meta_and_id(monkeypatch):
    monkeypatch.setattr(config_service, "get_pet_meta", lambda _base_id: None)
    monkeypatch.setattr(config_service, "get_pet_skill_meta", lambda _base_id: {"editor_name": "技能库名"})
    assert resolve_popular_skill_name(999, "") == "技能库名"

    monkeypatch.setattr(config_service, "get_pet_skill_meta", lambda _base_id: None)
    assert resolve_popular_skill_name(999, "") == "999"


def test_list_pets_with_learnable_skills_is_sorted_and_counts_skills():
    payload = list_pets_with_learnable_skills()

    assert payload["total"] > 0
    assert payload["pets"] == sorted(payload["pets"], key=lambda item: item["name"])
    assert all({"base_id", "name", "skill_count"}.issubset(item) for item in payload["pets"][:20])


def test_build_learnable_skill_payload_uses_skill_metadata():
    payload = build_learnable_skill_payload(7020360, {"skill_id": 7020360, "level_gain_skill": 7})

    assert payload["skill_id"] == 7020360
    assert payload["name"] == "抓挠"
    assert payload["source"] == 7
    assert "desc" in payload


def test_pet_learnable_skills_payload_contract_and_missing_pet():
    payload = pet_learnable_skills_payload(3001)

    assert payload is not None
    assert payload["base_id"] == 3001
    assert payload["name"] == "喵喵"
    assert len(payload["skills"]) > 0
    assert {"skill_id", "name", "element", "damage_type", "energy_cost", "power", "desc", "source"}.issubset(
        payload["skills"][0]
    )
    assert pet_learnable_skills_payload(999999999) is None
