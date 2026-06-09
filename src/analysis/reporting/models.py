"""战斗报告共享模型。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class BattleReportError(ValueError):
    """Raised when a requested report cannot be built."""


@dataclass(frozen=True)
class BattleBoundary:
    index: int
    enter_file: str
    finish_file: str
    enter_ts: str
    finish_ts: str
    enter_seconds: float
    finish_seconds: float
    incomplete: bool = False

    @property
    def duration(self) -> float:
        return max(0.0, self.finish_seconds - self.enter_seconds)


@dataclass(frozen=True)
class BattleReportSummary:
    report_id: str
    session_id: str
    battle_index: int
    enter_ts: str
    finish_ts: str
    duration_seconds: float
    complete: bool
    file_count: int
    battle_packet_count: int
    rounds: Optional[int]
    result: Optional[str]
    session_path: str
    archived: bool = False
    archive_path: Optional[str] = None


@dataclass(frozen=True)
class BattleReportDiagnostics:
    report_count: int
    packet_session_count: int
    packet_file_count: int
    latest_session_id: Optional[str]
    latest_session_path: Optional[str]
    latest_session_file_count: int
    battle_enter_count: int
    battle_finish_count: int
    completed_battle_count: int
    incomplete_battle_count: int
    has_battle_enter: bool
    has_battle_finish: bool

