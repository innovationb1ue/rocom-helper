"""战斗 sniffer 桥接过滤测试。"""
from __future__ import annotations

import asyncio

from src.analysis.constants import OPCODE_ACTION_RESOLVE, OPCODE_BATTLE_ENTER
from src.api.battle_sniffer_bridge import (
    BattleSnifferBridge,
    extract_battle_detail,
    should_process_battle_record,
)


class FakeSnifferManager:
    def __init__(self) -> None:
        self.callbacks = []

    def register_record_callback(self, callback):
        self.callbacks.append(callback)


def test_sniffer_record_filter_requires_clients():
    assert should_process_battle_record(
        {"opcode": OPCODE_BATTLE_ENTER},
        has_clients=False,
        battle_active=False,
    ) is False


def test_sniffer_record_filter_accepts_lifecycle_without_active_battle():
    assert should_process_battle_record(
        {"opcode": OPCODE_BATTLE_ENTER},
        has_clients=True,
        battle_active=False,
    ) is True


def test_sniffer_record_filter_rejects_in_battle_opcode_before_battle_active():
    assert should_process_battle_record(
        {"opcode": OPCODE_ACTION_RESOLVE},
        has_clients=True,
        battle_active=False,
    ) is False


def test_sniffer_record_filter_accepts_in_battle_opcode_when_active():
    assert should_process_battle_record(
        {"opcode": OPCODE_ACTION_RESOLVE},
        has_clients=True,
        battle_active=True,
    ) is True


def test_sniffer_record_filter_rejects_unknown_opcode():
    assert should_process_battle_record(
        {"opcode": 0xFFFF},
        has_clients=True,
        battle_active=True,
    ) is False


def test_extract_battle_detail_prefers_summary_detail_dict():
    assert extract_battle_detail({"_summary": {"detail": {"round": 3}, "kind": "x"}}) == {"round": 3}


def test_extract_battle_detail_falls_back_to_summary_dict():
    assert extract_battle_detail({"_summary": {"kind": "round_start"}}) == {"kind": "round_start"}


def test_extract_battle_detail_rejects_non_dict_values():
    assert extract_battle_detail({"_summary": {"detail": "bad"}}) == {}
    assert extract_battle_detail({"_summary": "bad"}) == {}


def test_battle_sniffer_bridge_registers_callback_once():
    manager = FakeSnifferManager()
    bridge = BattleSnifferBridge(
        has_clients=lambda: True,
        battle_active=lambda: True,
        process_event=lambda _opcode, _detail: asyncio.sleep(0),
        manager_provider=lambda: manager,
    )

    bridge.ensure_registered()
    bridge.ensure_registered()

    assert bridge.registered is True
    assert manager.callbacks == [bridge.handle_record]


def test_battle_sniffer_bridge_dispatches_accepted_record():
    async def _run():
        manager = FakeSnifferManager()
        calls = []

        async def process_event(opcode, detail):
            calls.append((opcode, detail))

        bridge = BattleSnifferBridge(
            has_clients=lambda: True,
            battle_active=lambda: True,
            process_event=process_event,
            manager_provider=lambda: manager,
        )

        bridge.handle_record({
            "opcode": OPCODE_ACTION_RESOLVE,
            "_summary": {"detail": {"round": 3}},
        })
        await asyncio.sleep(0)

        assert calls == [(OPCODE_ACTION_RESOLVE, {"round": 3})]

    asyncio.run(_run())


def test_battle_sniffer_bridge_skips_rejected_record_without_calling_active():
    async def _run():
        calls = []

        def battle_active():
            raise AssertionError("battle_active should not be checked without clients")

        async def process_event(opcode, detail):
            calls.append((opcode, detail))

        bridge = BattleSnifferBridge(
            has_clients=lambda: False,
            battle_active=battle_active,
            process_event=process_event,
            manager_provider=FakeSnifferManager,
        )

        bridge.handle_record({"opcode": OPCODE_ACTION_RESOLVE, "_summary": {"detail": {"round": 3}}})
        await asyncio.sleep(0)

        assert calls == []

    asyncio.run(_run())
