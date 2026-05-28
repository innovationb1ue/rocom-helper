"""战斗回放 API 的服务层。

路由层只处理 HTTP 参数和返回；这里集中 fixture 读取、协议 summarize 和
BattleManager 推送流程，避免 routes 直接依赖协议细节。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from src.analysis.constants import OPCODE_ROUND_START
from src.api.battle_manager import BattleManager


async def replay_fixture_to_manager(
    *,
    manager: BattleManager,
    session_dir: Path,
    delay_ms: int,
    stop_round: Optional[int],
) -> Dict[str, Any]:
    from src.protocol.opcodes import summarize
    from src.protocol.proto_core import extract_inner_message
    from tests.packet_reader import load_battle_packets

    packets = load_battle_packets(session_dir)
    if not packets:
        return {"status": "error", "message": "No battle packets found"}

    manager.reset_tracker()

    processed = 0
    total_formatted = 0
    stopped_early = False
    final_state: Dict[str, Any] = manager.get_state()

    for item in packets:
        record = item["record"]
        opcode = item["opcode"]

        inner = None
        if opcode == 0x0414:
            inner = extract_inner_message(record.get("root", {}))

        _kind, summary = summarize(record, inner)
        detail = summary.get("detail", summary) if isinstance(summary, dict) else {}
        if not isinstance(detail, dict):
            detail = {}

        if stop_round is not None and opcode == OPCODE_ROUND_START:
            current_round = manager.get_state().get("round", 0)
            incoming_round = detail.get("round", current_round + 1)
            if incoming_round > stop_round:
                stopped_early = True
                break

        result = await manager.process_event(opcode, detail, enable_archive=False)
        final_state = result.state
        processed += 1
        total_formatted += len(result.formatted_events)

        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

    return {
        "status": "ok",
        "processed": processed,
        "total_formatted_events": total_formatted,
        "result": final_state.get("result"),
        "rounds": final_state.get("round"),
        "stopped_early": stopped_early,
        "my_pets": len(final_state.get("my_pets", [])),
        "opp_pets": len(final_state.get("opp_pets", [])),
    }
