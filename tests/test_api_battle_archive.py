"""Battle archive helper tests."""
from __future__ import annotations

import asyncio
from pathlib import Path

import src.api.battle_archive as battle_archive
from src.analysis.constants import OPCODE_BATTLE_FINISH, OPCODE_ROUND_START


class FakeLogger:
    def __init__(self) -> None:
        self.infos = []
        self.exceptions = []

    def info(self, *args) -> None:
        self.infos.append(args)

    def exception(self, *args) -> None:
        self.exceptions.append(args)


def test_should_archive_completed_battle_only_on_enabled_finish_opcode():
    assert battle_archive.should_archive_completed_battle(
        OPCODE_BATTLE_FINISH,
        enable_archive=True,
    ) is True
    assert battle_archive.should_archive_completed_battle(
        OPCODE_BATTLE_FINISH,
        enable_archive=False,
    ) is False
    assert battle_archive.should_archive_completed_battle(
        OPCODE_ROUND_START,
        enable_archive=True,
    ) is False


def test_schedule_completed_battle_archive_starts_background_task_for_finish():
    calls = []

    async def archive():
        calls.append("archive")
        return "ok"

    async def _run():
        task = battle_archive.schedule_completed_battle_archive(
            OPCODE_BATTLE_FINISH,
            enable_archive=True,
            archive_coro_factory=archive,
        )
        assert task is not None
        assert await task == "ok"
        assert calls == ["archive"]

    asyncio.run(_run())


def test_schedule_completed_battle_archive_skips_when_disabled_or_not_finish():
    async def archive():
        raise AssertionError("should not run")

    async def _run():
        assert battle_archive.schedule_completed_battle_archive(
            OPCODE_BATTLE_FINISH,
            enable_archive=False,
            archive_coro_factory=archive,
        ) is None
        assert battle_archive.schedule_completed_battle_archive(
            OPCODE_ROUND_START,
            enable_archive=True,
            archive_coro_factory=archive,
        ) is None

    asyncio.run(_run())


def test_archive_completed_battle_returns_none_without_session_dir():
    async def _run():
        log = FakeLogger()
        result = await battle_archive.archive_completed_battle(
            session_dir_provider=lambda: None,
            archive_fn=lambda _session_dir: Path("unused"),
            log=log,
        )

        assert result is None
        assert log.infos == []
        assert log.exceptions == []

    asyncio.run(_run())


def test_archive_completed_battle_runs_archive_fn_in_thread_and_logs_success():
    async def _run():
        log = FakeLogger()
        calls = []

        def archive_fn(session_dir):
            calls.append(session_dir)
            return Path("archive.raco-report")

        result = await battle_archive.archive_completed_battle(
            session_dir_provider=lambda: Path("session"),
            archive_fn=archive_fn,
            log=log,
        )

        assert result == Path("archive.raco-report")
        assert calls == [Path("session")]
        assert log.infos == [("战斗报告已自动归档: %s", Path("archive.raco-report"))]
        assert log.exceptions == []

    asyncio.run(_run())


def test_archive_completed_battle_logs_and_swallows_archive_errors():
    async def _run():
        log = FakeLogger()

        def archive_fn(_session_dir):
            raise RuntimeError("boom")

        result = await battle_archive.archive_completed_battle(
            session_dir_provider=lambda: Path("session"),
            archive_fn=archive_fn,
            log=log,
        )

        assert result is None
        assert log.infos == []
        assert log.exceptions == [("自动归档战斗报告失败",)]

    asyncio.run(_run())
