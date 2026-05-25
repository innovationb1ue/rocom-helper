"""Central runtime configuration for the application."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_csv(name: str, default: Tuple[str, ...]) -> Tuple[str, ...]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class AppConfig:
    project_root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data" / "game"
    config_dir: Path = PROJECT_ROOT / "data" / "config"
    log_dir: Path = PROJECT_ROOT / "logs"
    api_host: str = os.getenv("RACO_API_HOST", "0.0.0.0")
    api_port: int = _env_int("RACO_API_PORT", 8000)
    frontend_port: int = _env_int("RACO_FRONTEND_PORT", 5173)
    capture_port: int = _env_int("RACO_CAPTURE_PORT", 8195)
    cors_origins: Tuple[str, ...] = _env_csv(
        "RACO_CORS_ORIGINS",
        ("http://localhost:5173", "http://127.0.0.1:5173"),
    )

    @property
    def session_key_file(self) -> Path:
        return self.log_dir / "session_key.txt"


settings = AppConfig()
