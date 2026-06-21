"""Configuration REST route action helper tests."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api import config_route_actions
from src.api.config_route_actions import (
    delete_popular_skill_payload,
    get_popular_skill_payload,
    list_popular_skills_payload,
    pet_learnable_skills_or_404,
    pets_with_learnable_skills_payload,
    update_popular_skill_payload,
)


def test_popular_skill_payloads_keep_contract(monkeypatch):
    saved = []
    monkeypatch.setattr(config_route_actions, "get_all_popular_skills", lambda: {"items": []})
    monkeypatch.setattr(config_route_actions, "get_popular_skills", lambda base_id: {"name": "喵喵", "skills": [1]})
    monkeypatch.setattr(config_route_actions, "resolve_popular_skill_name", lambda base_id, name: name or "解析名")
    monkeypatch.setattr(config_route_actions, "save_popular_skills", lambda *args: saved.append(args))
    monkeypatch.setattr(config_route_actions, "delete_popular_skills", lambda base_id: True)

    assert list_popular_skills_payload() == {"items": []}
    assert get_popular_skill_payload(3001) == {"base_id": 3001, "name": "喵喵", "skills": [1]}
    assert update_popular_skill_payload(3001, name="", skills=[1, 2], note="备注") == {
        "ok": True,
        "base_id": 3001,
        "name": "解析名",
        "skills": [1, 2],
    }
    assert saved == [(3001, "解析名", [1, 2], "备注")]
    assert delete_popular_skill_payload(3001) == {"ok": True, "base_id": 3001}


def test_popular_skill_payloads_translate_missing_to_404(monkeypatch):
    monkeypatch.setattr(config_route_actions, "get_popular_skills", lambda base_id: None)
    with pytest.raises(HTTPException) as exc_info:
        get_popular_skill_payload(999)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "No preset found for this pet"

    monkeypatch.setattr(config_route_actions, "delete_popular_skills", lambda base_id: False)
    with pytest.raises(HTTPException) as exc_info:
        delete_popular_skill_payload(999)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "No preset found for this pet"


def test_learnable_skill_payloads_keep_contract_and_404(monkeypatch):
    monkeypatch.setattr(config_route_actions, "list_pets_with_learnable_skills", lambda: {"total": 1})
    monkeypatch.setattr(
        config_route_actions,
        "pet_learnable_skills_payload",
        lambda base_id: {"base_id": base_id, "skills": []} if base_id == 3001 else None,
    )

    assert pets_with_learnable_skills_payload() == {"total": 1}
    assert pet_learnable_skills_or_404(3001) == {"base_id": 3001, "skills": []}

    with pytest.raises(HTTPException) as exc_info:
        pet_learnable_skills_or_404(999)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Pet not found in skill map"
