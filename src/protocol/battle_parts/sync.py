"""Small sync-data helpers for battle protocol extraction."""
from __future__ import annotations

from typing import Any, Dict


def compact_optional(data: Dict[str, Any]) -> Dict[str, Any]:
    """Drop None values while preserving falsey protocol values such as 0."""
    return {key: value for key, value in data.items() if value is not None}
