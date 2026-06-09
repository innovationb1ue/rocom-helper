"""Configuration REST route action helpers."""
from __future__ import annotations

from typing import Any, List

from fastapi import HTTPException

from src.api.config_service import (
    list_pets_with_learnable_skills,
    pet_learnable_skills_payload,
    resolve_popular_skill_name,
)
from src.data.loader import (
    delete_popular_skills,
    get_all_popular_skills,
    get_popular_skills,
    save_popular_skills,
)


def list_popular_skills_payload() -> Any:
    return get_all_popular_skills()


def get_popular_skill_payload(base_id: int) -> dict:
    preset = get_popular_skills(base_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="No preset found for this pet")
    return {"base_id": base_id, **preset}


def update_popular_skill_payload(base_id: int, *, name: str, skills: List[int], note: str) -> dict:
    resolved_name = resolve_popular_skill_name(base_id, name)
    save_popular_skills(base_id, resolved_name, skills, note)
    return {"ok": True, "base_id": base_id, "name": resolved_name, "skills": skills}


def delete_popular_skill_payload(base_id: int) -> dict:
    found = delete_popular_skills(base_id)
    if not found:
        raise HTTPException(status_code=404, detail="No preset found for this pet")
    return {"ok": True, "base_id": base_id}


def pets_with_learnable_skills_payload() -> dict:
    return list_pets_with_learnable_skills()


def pet_learnable_skills_or_404(base_id: int) -> dict:
    payload = pet_learnable_skills_payload(base_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Pet not found in skill map")
    return payload
