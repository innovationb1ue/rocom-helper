"""战斗抓包桥接的纯过滤/提取逻辑。"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict

from src.analysis.constants import AUX_BATTLE_OPCODES, IN_BATTLE_OPCODES, LIFECYCLE_OPCODES

ProcessEvent = Callable[[int, Dict[str, Any]], Awaitable[Any]]
SnifferManagerProvider = Callable[[], Any]


def should_process_battle_record(
    record: Dict[str, Any],
    *,
    has_clients: bool,
    battle_active: bool,
) -> bool:
    """判断抓包 record 是否应该进入实时战斗处理管线。"""
    if not has_clients:
        return False
    opcode = record.get("opcode")
    if opcode is None:
        return False
    if opcode not in LIFECYCLE_OPCODES and opcode not in IN_BATTLE_OPCODES and opcode not in AUX_BATTLE_OPCODES:
        return False
    if opcode not in LIFECYCLE_OPCODES and not battle_active:
        return False
    return True


def extract_battle_detail(record: Dict[str, Any]) -> Dict[str, Any]:
    """从 sniffer record 的摘要中提取 BattleProcessor 需要的 detail dict。"""
    summary = record.get("_summary", {})
    if not isinstance(summary, dict):
        return {}
    detail = summary.get("detail", summary)
    return detail if isinstance(detail, dict) else {}


def sniffer_manager_provider() -> Any:
    from src.api.sniffer_manager import get_sniffer_manager

    return get_sniffer_manager()


class BattleSnifferBridge:
    """把 sniffer record 转发到实时战斗处理管线。"""

    def __init__(
        self,
        *,
        has_clients: Callable[[], bool],
        battle_active: Callable[[], bool],
        process_event: ProcessEvent,
        manager_provider: SnifferManagerProvider = sniffer_manager_provider,
    ) -> None:
        self._has_clients = has_clients
        self._battle_active = battle_active
        self._process_event = process_event
        self._manager_provider = manager_provider
        self._registered = False

    @property
    def registered(self) -> bool:
        return self._registered

    def ensure_registered(self) -> None:
        if self._registered:
            return
        self._registered = True
        self._manager_provider().register_record_callback(self.handle_record)

    def handle_record(self, record: Dict[str, Any]) -> None:
        has_clients = self._has_clients()
        if not should_process_battle_record(
            record,
            has_clients=has_clients,
            battle_active=self._battle_active() if has_clients else False,
        ):
            return
        opcode = record["opcode"]
        detail = extract_battle_detail(record)
        asyncio.create_task(self._process_event(opcode, detail))
