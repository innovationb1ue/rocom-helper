"""DamageCalculator runtime configuration helpers."""
from __future__ import annotations

from typing import Any, Dict


def normalize_server_power_rules(rules: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Normalize direct or nested server power rule mappings.

    The public calculator accepts both ``{"skills": {...}}`` and the legacy
    direct ``{skill_id: rule}`` shape.  This helper keeps that compatibility
    out of the calculator facade.
    """
    raw = rules.get("skills", rules) if isinstance(rules, dict) else {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(skill_id): dict(rule)
        for skill_id, rule in raw.items()
        if isinstance(rule, dict)
    }
