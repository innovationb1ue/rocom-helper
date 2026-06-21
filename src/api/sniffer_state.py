"""Sniffer 当前状态快照到 manager 状态迁移的纯评估逻辑。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class SnifferStatusEvaluation:
    """对一次 sniffer status 快照的评估结果。"""

    flow_count: int
    next_state: Optional[str] = None
    next_message: Optional[str] = None


def evaluate_sniffer_status(
    status: Dict[str, Any],
    *,
    current_state: str,
    key_hex: Optional[str],
) -> SnifferStatusEvaluation:
    """根据 Sniffer.get_status() 输出决定 manager 是否需要推进状态。"""
    flow_count = max(0, int(status.get("flow_count", 0) or 0))
    if flow_count == 0:
        return SnifferStatusEvaluation(flow_count=0)

    flows = status.get("flows", [])
    any_has_key = any(
        isinstance(flow, dict) and bool(flow.get("has_key"))
        for flow in flows
    )
    if any_has_key or key_hex:
        return SnifferStatusEvaluation(
            flow_count=flow_count,
            next_state="key_captured",
            next_message="密钥已获取，正在监听数据",
        )
    if current_state == "listening":
        return SnifferStatusEvaluation(
            flow_count=flow_count,
            next_state="connected",
            next_message="游戏已连接，等待密钥...",
        )
    return SnifferStatusEvaluation(flow_count=flow_count)
